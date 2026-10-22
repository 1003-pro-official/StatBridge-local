from __future__ import annotations
from statbridge_mcp.observability import observed, record_failure

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class StatBridgeGraphState(TypedDict, total=False):
    """State shared only by the orchestration layer.

    Domain results remain ordinary dictionaries produced by StatBridgeAgent.
    This keeps the dictionary resolver, API-plan builder and MCP data layer
    independent from LangGraph.
    """

    query: str
    conversation_state: dict[str, Any] | None
    clarification: dict[str, str] | None
    resolution: dict[str, Any] | None
    execute: bool
    start_period: str | None
    end_period: str | None
    period_overrides: dict[str, tuple[str, str]] | None
    generate_answer: bool
    output_request: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    result: dict[str, Any]
    orchestration_stage: str
    orchestration_path: list[str]
    derived_planning: dict[str, Any]
    derived_responses: dict[str, Any]


class StatBridgeWorkflow:
    """LangGraph orchestration around the existing StatBridge domain methods."""

    def __init__(self, agent: Any, output_agent: Any | None = None) -> None:
        self.agent = agent
        self.output_agent = output_agent
        self.derived_runtime = None
        builder = StateGraph(StatBridgeGraphState)
        builder.add_node("resolve_request", self._resolve_request)
        builder.add_node("await_clarification", self._await_clarification)
        builder.add_node("finish_unresolved", self._finish_unresolved)
        builder.add_node("execute_statistics", self._execute_statistics)
        builder.add_node("prepare_output", self._prepare_output)
        builder.add_node('classify_analysis_intent', lambda state: {
            'orchestration_stage': 'derived_intent_classified',
            'orchestration_path': self._path(state, 'classify_analysis_intent')})
        builder.add_edge('classify_analysis_intent', 'plan_derived_indicator')
        builder.add_node("plan_derived_indicator", self._plan_derived_indicator)
        builder.add_node("validate_derived_plan", self._validate_derived_plan)
        builder.add_node("execute_derived_sources", self._execute_derived_sources)
        builder.add_node("calculate_derived_indicator", self._calculate_derived_indicator)
        builder.add_node("finish_derived", lambda state: {})
        for node, target in (("plan_derived_indicator", "validate_derived_plan"),
                             ("validate_derived_plan", "execute_derived_sources"),
                             ("execute_derived_sources", "calculate_derived_indicator"),
                             ("calculate_derived_indicator", "prepare_output")):
            builder.add_conditional_edges(node, self._route_derived,
                                          {"continue": target, "stop": "finish_derived"})
        builder.add_edge("finish_derived", END)
        builder.add_conditional_edges(
            START,
            self._route_start,
            {"input": "resolve_request", "output": "prepare_output", "derived": "classify_analysis_intent"},
        )
        builder.add_conditional_edges(
            "resolve_request",
            self._route_after_resolution,
            {
                "clarification": "await_clarification",
                "unresolved": "finish_unresolved",
                "resolved": "execute_statistics",
            },
        )
        builder.add_edge("await_clarification", END)
        builder.add_edge("finish_unresolved", END)
        builder.add_conditional_edges(
            "execute_statistics",
            self._route_after_execution,
            {"await_output": "await_output_selection", "prepare_output": "prepare_output"},
        )
        builder.add_node("await_output_selection", self._await_output_selection)
        builder.add_edge("await_output_selection", END)
        builder.add_edge("prepare_output", END)
        self.graph = builder.compile(name="statbridge-agent-orchestration")

    @staticmethod
    def _path(state: StatBridgeGraphState, node: str) -> list[str]:
        return [*(state.get("orchestration_path") or []), node]

    @observed('request.resolve', 'span')
    def _resolve_request(self, state: StatBridgeGraphState) -> dict[str, Any]:
        resolution = state.get("resolution")
        if resolution is None:
            resolution = self.agent.resolve(
                query=state["query"],
                state=state.get("conversation_state"),
                clarification=state.get("clarification"),
            )
        return {
            "resolution": resolution,
            "orchestration_stage": "resolved_request",
            "orchestration_path": self._path(state, "resolve_request"),
        }

    @observed('intent.route', 'span')
    def _route_start(self, state: StatBridgeGraphState):
        if state.get("execution_result") is not None:
            return "output"
        from derived_indicator_planner import is_derived_request
        if self.derived_runtime and (is_derived_request(state.get('query', '')) or
                                     (state.get('conversation_state') or {}).get('_derived_query')):
            return "derived"
        return "input"

    @staticmethod
    def _route_derived(state):
        return 'stop' if (state.get('result') or {}).get('derived_blocked') else 'continue'

    def _derived_failure(self, state, stage, message):
        record_failure(message)
        planning = state.get('derived_planning') or {}
        continuation = self._derived_context(state)
        failure_kind = getattr(message, 'failure_kind', 'analysis_error')
        self.derived_runtime.evidence.save({'query': state['query'], 'status': 'failed', 'stage': stage,
            'failure_kind': failure_kind,
            'error': str(message), 'plan': planning['plan'].model_dump() if planning.get('plan') else None,
            'catalog_version': self.derived_runtime.catalog.version, 'planner_trace': getattr(message, 'evidence', None),
            'usage': planning.get('usage')})
        status = ('need_details' if failure_kind == 'validation_error' and stage in
                  {'validate_derived_plan', 'calculate_derived_indicator'} else 'data_unavailable')
        return {'result': {'status': status, 'query': state['query'], 'derived_blocked': True,
                           'failure_kind': failure_kind, 'failure_stage': stage,
                           'question': str(message), 'state': continuation},
                'orchestration_stage': stage, 'orchestration_path': self._path(state, stage)}

    @staticmethod
    def _derived_context(state, query=None):
        prior = dict(state.get('conversation_state') or {})
        original = prior.get('_derived_query')
        combined = query or (f'{original}\n추가 조건: {state["query"]}' if original and original != state['query'] else state['query'])
        return {**prior, '_derived_query': combined,
                '_derived_start': state.get('start_period') or prior.get('_derived_start'),
                '_derived_end': state.get('end_period') or prior.get('_derived_end')}

    @observed('planner.plan', 'span')
    def _plan_derived_indicator(self, state):
        prior = (state.get('conversation_state') or {}).get('_derived_query')
        query = f'{prior}\n추가 조건: {state["query"]}' if prior and prior != state['query'] else state['query']
        try:
            continuation = self._derived_context(state, query)
            planning = self.derived_runtime.plan(query, start_period=continuation.get('_derived_start'), end_period=continuation.get('_derived_end'))
            if planning['status'] != 'planned':
                self.derived_runtime.evidence.save({'query': query, 'catalog_version': self.derived_runtime.catalog.version,
                    'status': planning['status'], 'missing': planning.get('missing'), 'searches': planning.get('searches'),
                    'usage': planning.get('usage'), 'question': planning.get('question'), 'availability':planning.get('availability')})
                return {'result': {**planning, 'query': query, 'derived_blocked': True, 'state': continuation},
                        'orchestration_stage': 'awaiting_derived_details',
                        'orchestration_path': self._path(state, 'plan_derived_indicator')}
            return {'derived_planning': planning, 'orchestration_path': self._path(state, 'plan_derived_indicator')}
        except (ValueError, TypeError, KeyError) as exc:
            return self._derived_failure(state, 'plan_derived_indicator', exc)

    @observed('plan.validate', 'span')
    def _validate_derived_plan(self, state):
        try:
            planning = dict(state['derived_planning'])
            planning['bounds'] = self.derived_runtime.validate(planning['plan'])
            if not state.get('execute', True):
                self.derived_runtime.evidence.save({'query': state['query'], 'status': 'planned_only',
                    'plan': planning['plan'].model_dump(), 'bounds': planning['bounds'],
                    'catalog_version': self.derived_runtime.catalog.version, 'usage': planning.get('usage'),
                    'searches': planning.get('searches'), 'semantic_review': planning.get('semantic_review')})
                return {'result': {'status': 'resolved', 'derived_blocked': True,
                                  'execution': {'status': 'planned_only'}, 'plan': planning['plan'].model_dump(),
                                  'question': '계산 계획을 검증했습니다. 실제 데이터 조회는 생략했습니다.'},
                        'orchestration_path': self._path(state, 'validate_derived_plan')}
            return {'derived_planning': planning, 'orchestration_path': self._path(state, 'validate_derived_plan')}
        except (ValueError, TypeError, KeyError) as exc:
            return self._derived_failure(state, 'validate_derived_plan', exc)

    @observed('sources.fetch', 'span')
    def _execute_derived_sources(self, state):
        try:
            planning = state['derived_planning']
            return {'derived_responses': self.derived_runtime.fetch(planning['plan'], planning['bounds']),
                    'orchestration_path': self._path(state, 'execute_derived_sources')}
        except (ValueError, TypeError, KeyError) as exc:
            return self._derived_failure(state, 'execute_derived_sources', exc)

    @observed('dag.calculate', 'span')
    def _calculate_derived_indicator(self, state):
        try:
            return {'result': self.derived_runtime.calculate(state['query'], state['derived_planning'], state['derived_responses']),
                    'orchestration_stage': 'derived_calculated',
                    'orchestration_path': self._path(state, 'calculate_derived_indicator')}
        except (ValueError, TypeError, KeyError) as exc:
            return self._derived_failure(state, 'calculate_derived_indicator', exc)

    @staticmethod
    def _route_after_resolution(
        state: StatBridgeGraphState,
    ) -> Literal["clarification", "unresolved", "resolved"]:
        status = str((state.get("resolution") or {}).get("status") or "")
        if status == "need_clarification":
            return "clarification"
        if status != "resolved":
            return "unresolved"
        return "resolved"

    @staticmethod
    def _route_after_execution(state: StatBridgeGraphState) -> Literal["await_output", "prepare_output"]:
        execution_status = str(((state.get("result") or {}).get("execution") or {}).get("status") or "")
        request = state.get("output_request") or {}
        return "prepare_output" if execution_status == "success" and request.get("chart_type") else "await_output"

    @observed('request.clarify', 'span')
    def _await_clarification(self, state: StatBridgeGraphState) -> dict[str, Any]:
        return {
            "result": state.get("resolution") or {},
            "orchestration_stage": "awaiting_clarification",
            "orchestration_path": self._path(state, "await_clarification"),
        }

    def _finish_unresolved(self, state: StatBridgeGraphState) -> dict[str, Any]:
        return {
            "result": state.get("resolution") or {},
            "orchestration_stage": "unresolved",
            "orchestration_path": self._path(state, "finish_unresolved"),
        }

    @observed('statistics.execute', 'span')
    def _execute_statistics(self, state: StatBridgeGraphState) -> dict[str, Any]:
        result = self.agent.execute_resolution(
            query=state["query"],
            resolution=state.get("resolution") or {},
            execute=state.get("execute", True),
            start_period=state.get("start_period"),
            end_period=state.get("end_period"),
            period_overrides=state.get("period_overrides"),
            generate_answer=state.get("generate_answer", True),
        )
        execution_status = str((result.get("execution") or {}).get("status") or "")
        return {
            "result": result,
            "orchestration_stage": "executed" if execution_status == "success" else execution_status or "execution_finished",
            "orchestration_path": self._path(state, "execute_statistics"),
        }

    @observed('output.prepare', 'span')
    def _prepare_output(self, state: StatBridgeGraphState) -> dict[str, Any]:
        result = dict(state.get("execution_result") or state.get("result") or {})
        execution_status = str((result.get("execution") or {}).get("status") or "")
        if result.get('derivedEvidence') and not (state.get('output_request') or {}).get('chart_type'):
            return {'result': result, 'orchestration_stage': 'awaiting_output_selection', 'orchestration_path': self._path(state, 'prepare_output')}
        if self.output_agent is not None and execution_status == "success":
            result["output"] = self.output_agent.prepare(result, state.get("output_request"))
        return {
            "result": result,
            "orchestration_stage": "output_ready" if result.get("output") else state.get("orchestration_stage", "execution_finished"),
            "orchestration_path": self._path(state, "prepare_output"),
        }

    def _await_output_selection(self, state: StatBridgeGraphState) -> dict[str, Any]:
        return {
            "result": state.get("result") or {},
            "orchestration_stage": "awaiting_output_selection",
            "orchestration_path": self._path(state, "await_output_selection"),
        }

    def invoke(
        self,
        *,
        query: str,
        conversation_state: dict[str, Any] | None = None,
        clarification: dict[str, str] | None = None,
        resolution: dict[str, Any] | None = None,
        execute: bool = True,
        start_period: str | None = None,
        end_period: str | None = None,
        period_overrides: dict[str, tuple[str, str]] | None = None,
        generate_answer: bool = True,
        output_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.graph.invoke({
            "query": query,
            "conversation_state": conversation_state,
            "clarification": clarification,
            "resolution": resolution,
            "execute": execute,
            "start_period": start_period,
            "end_period": end_period,
            "period_overrides": period_overrides,
            "generate_answer": generate_answer,
            "output_request": output_request,
            "execution_result": None,
            "orchestration_path": [],
        })
        result = dict(state.get("result") or {})
        result["orchestration"] = {
            "engine": "langgraph",
            "stage": state.get("orchestration_stage") or "unknown",
            "path": state.get("orchestration_path") or [],
        }
        return result

    def invoke_output(self, *, result: dict[str, Any], output_request: dict[str, Any]) -> dict[str, Any]:
        state = self.graph.invoke({
            "execution_result": result,
            "output_request": output_request,
            "orchestration_path": list((result.get("orchestration") or {}).get("path") or []),
        })
        rendered = dict(state.get("result") or {})
        rendered["orchestration"] = {
            "engine": "langgraph",
            "stage": state.get("orchestration_stage") or "unknown",
            "path": state.get("orchestration_path") or [],
        }
        return rendered
