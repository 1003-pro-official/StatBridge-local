# StatBridge 문서

[프로젝트 소개](../README.md) · [실행 안내](getting-started.md) · [기여 규칙](../CONTRIBUTING.md)

## 시스템 설계

| 주제 | 문서 |
| --- | --- |
| 화면에서 원자료 조회까지 | [UI → Agent → 통계표 탐색 흐름](architecture/STATBRIDGE_UI_TO_TABLE_RETRIEVAL_FLOW_DETAILED.md) |
| 에이전트의 상태와 단계 | [LangGraph 오케스트레이션](architecture/LANGGRAPH_ORCHESTRATION.md) |
| 그래프와 표 생성 | [OutputAgent 구조](architecture/OUTPUT_AGENT_ARCHITECTURE.md) |
| MCP 서버와 호출 경계 | [MCP 실행 안내](implementation/MCP_RUNTIME_GUIDE.md) |
| 실행 시간과 장애 진단 | [Langfuse 계측](implementation/2026-10-20-langfuse-instrumentation.md) |

## 기능별 문서

| 기능 | 문서 |
| --- | --- |
| 한국은행 통계표와 분류 | [통계표 목록](data/한국은행-통계표-목록.md) |
| 여러 계열과 후속 질문 | [질의 범위와 출력 정합성](implementation/2026-10-27-query-scope-and-export-fix.md) |
| 파생지표 계획과 검증 | [동적 파생지표 설계](implementation/2026-10-19-dynamic-derived-design.md) · [원자료와 계산 결과 출력](implementation/2026-10-27-derived-output-fix.md) |
| 원자료가 부족한 경우 | [파일 형식과 입수처](derived_file_formats_and_sources.md) · [업로드 후 계산 흐름](derived_upload_flow.md) |
| 그래프 편집과 파일 출력 | [그래프 편집 화면](chart_workspace_ux.md) · [자연어 편집 명령](chart_edit_commands.md) · [스냅샷 출력 개선](implementation/2026-10-14-snapshot-report-quality.md) |
| 표 편집과 참고 자료 | [표 편집 및 참고 파일](implementation/2026-10-19-table-preview-flow-reference-fix.md) |
| 분석 결과에 대한 대화 | [보고서 대화 구현](implementation/2026-10-20-report-conversation.md) |

## 평가와 개발 이력

- [공개 평가 자료 색인](../eval/README.md)에서 평가 계열별 데이터셋과 실행 방법을 찾을 수 있습니다.
- [최소 E2E 평가 이력](evaluation/min-e2e-history/README.md)과 [v2.2 평가 설계](evaluation/2026-11-03-v22-evaluation-set.md)에 버전별 실행 범위와 결과 해석을 기록했습니다.
- [3인 정성평가](evaluation/2026-11-03-qualitative-10-3p.md)와 [RAGAS·LLM Judge](evaluation/2026-11-02-ragas-llm-judge.md)는 각 검토 방식과 한계를 다룹니다.
- [구현 기록](implementation/)과 [주차별 기록](weeks/)에서 개발 과정과 검증 이력을 확인할 수 있습니다.
- 정리 전 README의 상세 변경 기록은 [이전 README](https://github.com/1003-pro-official/StatBridge-local/blob/a2a5f2171de6590cf07b68957177de85c33416f0/README.md)에서 확인할 수 있습니다.
