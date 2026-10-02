# StatBridge v4.1 Holdout 구조 개선 보고서

## 1. 작업 범위와 보호 원칙

- 대상: `StatBridge1/StatBridge-official` 현재 작업본
- 개발 기준: Golden v4.1 공개 120건과 과거 private holdout 30건
- private 30건은 이미 정답이 공개된 과거 평가셋이므로 blind 성능이 아니라 regression/error-development 결과로 취급한다.
- `C:\Users\김민\Desktop\경진대회\golden-set`의 차기 최종 Golden Set은 열거나 검색하지 않았다.
- runtime에 Golden ID, 전체 query 문장, query→정답 table ID 매핑을 추가하지 않았다.
- LLM의 table/item/objL ID 생성이나 기존 KOSIS/MCP 안전장치를 변경하지 않았다.

## 2. 수정 전 재현

### 공개 v4.1 120건

| 지표 | Baseline |
|---|---:|
| 최종 status | 120/120 (100%) |
| 최종 exact table set | 120/120 (100%) |
| Raw Recall@1 | 89.13% |
| Raw Recall@5 | 92.39% |

### 과거 private holdout 30건

| 지표 | Baseline |
|---|---:|
| Status accuracy | 90.00% |
| Exact case accuracy | 70.00% |
| Table-set precision | 84.62% |
| Table-set recall | 75.86% |
| Table-set F1 | 80.00% |
| Raw Recall@1 | 82.61% |
| Raw Recall@5 | 91.30% |

private scorer가 `status/table_ids`만 읽던 문제를 확인했고, `predicted_status/predicted_table_ids` 형식도 명시적으로 처리하도록 수정했다.

## 3. 실패 유형 분석

수정 전 private 최종 실패는 9건이었다.

- Retrieval coverage: 넓은 표현의 핵심 표가 modifier 위주의 후보에 밀림.
- Multi-series decomposition: 명시한 2~3개 series 중 하나만 최종 선택.
- Clarify vs no_match: 지원 영역인 넓은 채권·수신 개념을 no_match로 종료.
- no_match false positive: 지원하지 않는 핵심 metric 대신 `지역별` modifier만 맞는 금융표 선택.
- Followup ADD: “같이” 추가한 신규 series 또는 기존 series가 소실.
- Followup REPLACE: 명목→시가, 실적→전망 변경에서 과거 조건이 잔존.

## 4. 변경 내용과 이유

### `stat_language_resolver.py`

- `QueryState`를 추가했다. 필드는 metrics, subjects, regions, institutions, company_sizes, measure_basis, valuation_basis, frequency, period, comparison, series다.
- 후속 발화를 `KEEP`, `SET`, `REPLACE`, `ADD`, `REMOVE`, `CLEAR` operation으로 변환하고 before/after/evidence를 trace에 남긴다.
- 현재 발화의 명시적 변경을 이전 state보다 우선한다.
- ADD는 이전 series를 보존한 뒤 새 metric을 기관·측정기준 문맥 안에서 독립 검색한다.
- REPLACE는 수출/수입, 신규취급액/잔액, 실적/전망, 명목/시가/실질 등의 일반 변경 축으로 sibling을 찾는다.
- comma·와/과·그리고·및 등으로 명시된 series를 각각 독립 검색한다. 후보가 많다는 이유만으로 multi로 만들지는 않는다.
- table/alias의 `표·통계·자료·지수` 접미어를 제거한 core phrase를 검색 근거로 사용한다.
- 지역·기간 같은 modifier보다 core metric을 먼저 확인한다. catalog에 없는 명시적 사용량 metric은 modifier 후보를 반환하지 않는다.
- dimension 복합값은 질의에서 두 개 이상의 구성요소가 함께 확인될 때만 강화한다. 단일 일반어가 대량 후보를 오염시키지 않게 했다.
- 반복 core-metric 검사를 위해 catalog 검색 문자열을 초기화 시 한 번만 생성한다.

### `clarification_extensions.json`

- 지원 domain 안의 넓은 채권 자료와 금융기관 수신 자료에 일반 clarification group을 추가했다.
- 대외채권처럼 이미 구체적인 개념에는 불필요한 clarification이 발생하지 않도록 skip 조건을 둔다.

### 평가 도구

- `evaluate_holdout_predictions.py`: query-only 입력으로 prediction과 typed-state 실행 trace를 생성한다. 정답 파일을 읽지 않는다.
- private `score_holdout.py`: 두 prediction schema를 모두 명확하게 처리한다.

## 5. 수정 후 공개 120 결과

| 지표 | Baseline | Final |
|---|---:|---:|
| 최종 status | 100% | **100%** |
| 최종 exact table set | 100% | **100%** |
| Raw Recall@1 | 89.13% | **92.39%** |
| Raw Recall@3 | 91.30% | **94.57%** |
| Raw Recall@5 | 92.39% | **95.65%** |
| MRR | 0.9049 | **0.9375** |
| Multi exact set | 100% | **100%** |
| Followup | 100% | **100%** |
| Clarify / no_match / catalog_only | 100% | **100%** |

Dev 50건과 test 70건 모두 최종 decision/exact set 100%를 유지했다.

## 6. 수정 후 과거 private 30 결과

| 지표 | Baseline | Final |
|---|---:|---:|
| Status accuracy | 90.00% | **100%** |
| Exact case accuracy | 70.00% | **100%** |
| Table-set precision | 84.62% | **100%** |
| Table-set recall | 75.86% | **100%** |
| Table-set F1 | 80.00% | **100%** |
| Raw Recall@1 | 82.61% | **91.30%** |
| Raw Recall@3 | 91.30% | **95.65%** |
| Raw Recall@5 | 91.30% | **95.65%** |
| Raw MRR | 기록 0.8623 | **0.9348** |

유형별 exact는 single, multi, clarify, no_match, catalog_only, followup 모두 100%다. 이는 과거 private 정답을 오류분석에 사용한 개발셋 성능이며 새로운 blind 성능으로 해석하지 않는다.

## 7. Trace

`v41_holdout_patch_trace.jsonl`은 각 케이스에 다음을 기록한다.

- query
- previous_state
- parsed_operations
- effective_query_state
- raw_top5
- series_requests / selected_series
- predicted_status / predicted_table_ids
- failure_stage / execution_path
- 단계별 timings_ms

최종 결과가 raw Top-5와 달라지는 followup/multi 사례는 `parsed_operations`와 `execution_path`로 변경 근거를 확인할 수 있다.

## 8. 성능

대표 질의 3건의 resolver 측정은 cold 합계 1,705.94ms, 동일 인스턴스 반복 합계 1.22ms, 반복 질의당 0.41ms였다. 이 값은 로컬 resolver 구간이며 NCP/KOSIS 네트워크 왕복은 포함하지 않는다.

## 9. Regression 및 안전 계약

- Python compile: 통과
- `tests/TEST_AGENT_FLOW.py`: 통과
- HCX clarification hard constraint: 통과
- dictionary ID 기반 MCP plan: 통과
- KOSIS exact params 및 item/objL 전달: 통과
- frontend `tsc --noEmit && vite build`: 통과
- 공개 120 최종 regression: 통과
- 과거 private 30 regression: 통과
- 실패 파일: 0건

## 10. 남은 실패와 제한

- 공개·과거 private의 최종 실패는 0건이다.
- 원시 retrieval은 공개 R@5 95.65%, private R@5 95.65%로 100%가 아니다. 최종 composition/state 단계가 일부를 복원한다.
- 과거 private를 개발에 사용했으므로 향후 일반화 성능은 차기 query-only blind 평가로 별도 측정해야 한다.
- 이번 결과를 새로운 질의나 차기 비공개 Golden Set의 100% 성능 주장으로 사용하면 안 된다.

## 11. 하드코딩·누출 점검

- production runtime에서 Golden ID 참조 없음.
- query 전체 문장 비교 분기 없음.
- query→정답 table ID lookup 없음.
- holdout answer runtime 참조 없음.
- 팀원 차기 Golden Set 접근 없음.
- 추가한 규칙은 통계 개념, 변경 축, core/modifier, dimension 구성요소에 대한 일반 규칙이다.
