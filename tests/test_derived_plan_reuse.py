"""Cache boundary regressions; synthetic plans, no provider calls."""
import copy
from contextvars import ContextVar
from types import SimpleNamespace
import sys
import pytest
from derived_indicator_runtime import DerivedIndicatorRuntime
from derived_indicator_planner import DerivedIndicatorPlanner
from derived_plan_cache import VerifiedPlanCache
from statbridge_mcp.metadata_store import MetadataStore
from test_dynamic_derived_indicators import plan, Model


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    actor = ContextVar('reuse_test_actor', default={'id': 1})
    monkeypatch.setitem(sys.modules, 'account_auth', SimpleNamespace(USER=actor))
    runtime = DerivedIndicatorRuntime(SimpleNamespace(service=SimpleNamespace(store=MetadataStore())), Model([]), tmp_path)
    p = plan(runtime.catalog, 'inverse')
    result = {'status': 'planned', 'plan': p, 'bounds': runtime.validate(p),
              'semantic_review': {'approved': True, 'reason': 'synthetic test'}, 'usage': [{'stage': 'semantic_review'}]}
    calls = []
    def fresh(query, **kwargs):
        calls.append(query)
        return copy.deepcopy(result)
    monkeypatch.setattr(runtime, '_plan_uncached', fresh)
    runtime.test_result, runtime.test_calls, runtime.actor = result, calls, actor
    return runtime


def test_same_owner_reuses_semantically_reviewed_plan_but_not_values(runtime):
    first = runtime.plan('exact question')
    first['plan'].indicator_name = 'caller mutation'
    second = runtime.plan('exact question')
    assert len(runtime.test_calls) == 1
    assert second['plan_cache_hit'] and second['usage'] == []
    assert second['semantic_review']['approved'] is True
    assert second['plan_reuse']['semantic_review_reused'] is True
    assert second['plan'].indicator_name != 'caller mutation'
    assert 'source_data' not in second


@pytest.mark.parametrize('change', ['owner', 'query', 'period', 'policy', 'catalog', 'metadata', 'expiry'])
def test_changed_contract_cannot_reuse(runtime, monkeypatch, change):
    now = [1.0]
    runtime.plan_cache.clock = lambda: now[0]
    runtime.plan('question')
    query, kwargs = 'question', {}
    if change == 'owner': runtime.actor.set({'id': 2})
    elif change == 'query': query = 'different question'
    elif change == 'period': kwargs['start_period'] = '202101'
    elif change == 'policy': runtime.plan_policy_hash = 'changed'
    elif change == 'catalog': runtime.catalog.version = 'changed'
    elif change == 'expiry': now[0] += 301
    elif change == 'metadata':
        original = runtime.catalog.get_table_metadata
        def altered(table):
            return {**original(table), 'comments': ['changed actual metadata']}
        monkeypatch.setattr(runtime.catalog, 'get_table_metadata', altered)
    assert not runtime.plan(query, **kwargs).get('plan_cache_hit')
    assert len(runtime.test_calls) == 2


@pytest.mark.parametrize('kind', ['unapproved', 'blocked', 'no_owner', 'file_catalog', 'previous'])
def test_unreviewed_or_contextual_requests_not_cached(runtime, kind):
    kwargs = {}
    if kind == 'unapproved': runtime.test_result['semantic_review']['approved'] = False
    elif kind == 'blocked': runtime.test_result['status'] = 'need_details'
    elif kind == 'no_owner': runtime.actor.set(None)
    elif kind == 'file_catalog': runtime.catalog.allow_file_inputs = True
    elif kind == 'previous': kwargs['previous'] = runtime.test_result['plan'].model_dump()
    runtime.plan('question', **kwargs)
    assert not runtime.plan('question', **kwargs).get('plan_cache_hit')
    assert len(runtime.test_calls) == 2


def test_prefetch_removes_tool_roundtrip_but_still_calls_semantic_review(runtime):
    runtime.catalog.supports_metadata_prefetch = True
    p = plan(runtime.catalog, 'inverse')
    model = Model([{'action': 'plan', 'plan': p.model_dump()}, {'approved': True, 'reason': 'synthetic review'}])
    result = DerivedIndicatorPlanner(model, runtime.catalog).plan('경제심리지수 원계열의 역수를 구해줘')
    assert result['status'] == 'planned'
    assert [u['stage'] for u in result['usage']] == ['planning', 'semantic_review']


def test_bounded_cache_evicts_and_returns_copies():
    cache = VerifiedPlanCache(capacity=1)
    cache.put('a', {'value': []}, 'sha')
    cache.get('a')['result']['value'].append(1)
    assert cache.get('a')['result']['value'] == []
    cache.put('b', {}, 'sha')
    assert cache.get('a') is None
