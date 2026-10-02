# STATBRIDGE Golden Set v4.1 평가 및 개선 보고서

평가일: 2026-09-28
평가 범위: 공개 라벨 dev 50건 + test 70건 = 120건
비공개 범위: holdout query 30건의 정답은 접근하거나 추정하지 않음

## 1. 수정 전 baseline

Baseline은 런타임 코드를 수정하기 전에 현재 deterministic resolver로 저장했다. 외부 NCP 호출은 샌드박스 프록시에서 차단되어 baseline 본평가에는 섞지 않았고, 승인된 네트워크 실행의 ablation에서 별도로 비교했다.

| 평가 | 건수 | R@1 | R@3 | R@5 | MRR | Top-1 | Multi exact | Clarify | No-match | Catalog-only | Followup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 전체 | 120 | 51.09% | 59.78% | 63.04% | 0.5603 | 51.09% | 0.00% | 43.75% | 100.00% | 0.00% | 12.50% |
| Final 전체 | 120 | 89.13% | 91.30% | 92.39% | 0.9049 | 89.13% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| Baseline dev | 50 | 50.00% | 57.89% | 60.53% | 0.5528 | 50.00% | 0.00% | 42.86% | 100.00% | 0.00% | 0.00% |
| Final dev | 50 | 94.74% | 94.74% | 94.74% | 0.9474 | 94.74% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| Baseline test | 70 | 51.85% | 61.11% | 64.81% | 0.5656 | 51.85% | 0.00% | 44.44% | 100.00% | 0.00% | 20.00% |
| Final test | 70 | 85.19% | 88.89% | 90.74% | 0.8750 | 85.19% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

Multi set baseline/final: precision 50.00% → 100.00%, recall 22.92% → 100.00%, F1 31.25% → 100.00%.

## 2. 유형별 baseline과 before/after

전체 exact-set 기준:

| 유형 | Baseline | Final |
|---|---:|---:|
| `catalog_only` | 0.00% | 100.00% |
| `clarify` | 87.50% | 100.00% |
| `followup` | 12.50% | 100.00% |
| `multi` | 0.00% | 100.00% |
| `no_match` | 100.00% | 100.00% |
| `single` | 64.58% | 100.00% |


## 3. 실패 원인 분석

Baseline 주요 실패는 query/status 17건, followup context 손실 16건, Top-1 reranking 11건, clarification 9건, multi 일부 누락 8건이었다. 원인은 관측기간을 점수에 반영하지 않은 점, 동일 도메인 전체에 넓게 복제된 semantic alias, 단일 Top-1 종료, 후속 발화 상태 미병합, catalog-only 상태 부재였다.

Final 최종 status/table-set 실패는 0건이다. 아래 `failure_counts`는 최종 결정과 별도로 저장한 원시 단일후보 retrieval trace의 순위 오류 분포다: `{"C: 정답이 Recall@5 밖": 7, "D: 정답 후보 존재하나 Top-1 실패": 3}`.

## 4. 수정한 파일 목록과 파일별 내용

- `src/agent/stat_dictionary/stat_language_resolver.py`: 관측기간 필터, 구체 표명 우선, query-score 캐시, 개념 근거 기반 no-match, 명시 비교 series 분해, 동일 통계군 sibling 판별, 생략형 후속 상태 복원, catalog-only 판정.
- `src/agent/stat_dictionary/clarification_extensions.json`: 일반 통계 개념의 역질문 그룹과 카탈로그 전용 표 소스. Golden query 문장이나 ID별 예외는 넣지 않음.
- `src/agent/statbridge_agent.py`: deterministic multi fallback, followup query 병합, 강한 사전 근거가 있는 질의의 HCX 우회 fast path. 선택 ID는 항상 resolver 사전에서만 사용.
- `src/agent/ncp_clova_client.py`: 반복 분류 결과를 제한 크기 LRU 캐시에 저장.
- `src/agent/ncp_retrieval_client.py`: 반복 embedding/rerank 결과를 제한 크기 LRU 캐시에 저장.
- `src/agent/hybrid_retriever.py`: 점수와 후보 간격이 충분한 정확 일치에 한해 외부 reranker 호출을 생략.
- `src/agent/bridge_api.py`: catalog-only UI 계약. 조회 파라미터가 없으면 KOSIS 호출을 중단.
- `tools/evaluate_golden_v41.py`: 상세 case trace 및 요구 지표 산출.
- `tools/evaluate_ablation_v41.py`: 동일 후보 trace 기반 5개 score 조합 비교.
- `tools/finalize_golden_v41.py`: machine-readable 산출물과 이 보고서 생성.

## 5. 수정 이유

변경은 dev 실패 유형에서 일반 규칙을 추출해 적용했다. 특정 query 문자열이나 Golden ID를 runtime 분기로 사용하지 않았다. 2025년 질의가 2012년 종료 표를 고르는 문제는 기간 호환성으로, 복수 지표 누락은 각 명시 series 독립 검색으로, 후속 조건 소실은 변경 축만 교체하는 state merge로 해결했다.

성능 측정에서 동일 resolver 인스턴스의 대표 질의 3건은 첫 실행 합계 1,144.79ms, 반복 실행 합계 0.88ms(질의당 0.29ms)였다. 이는 로컬 score 캐시 구간 측정이며, 최초 NCP/KOSIS 네트워크 왕복시간은 포함하지 않는다.

## 6. Ablation

| 조합 | 건수 | R@1 | R@3 | R@5 | MRR | Top-1 |
|---|---:|---:|---:|---:|---:|---:|
| `rule_only` | 120 | 69.57% | 82.61% | 84.78% | 0.7595 | 69.57% |
| `embedding_only` | 120 | 69.57% | 88.04% | 92.39% | 0.8010 | 69.57% |
| `rule_embedding` | 120 | 83.70% | 89.13% | 93.48% | 0.8776 | 83.70% |
| `embedding_reranker` | 120 | 72.83% | 89.13% | 92.39% | 0.8219 | 72.83% |
| `rule_embedding_reranker` | 120 | 83.70% | 91.30% | 93.48% | 0.8812 | 83.70% |

가중치는 이번 패치에서 임의 변경하지 않았다. 표는 현행 score를 분해해 동일 후보에서 재정렬한 결과다.

## 7. 수정 후 dev/test 결과

상단 통합표 참조. 개발은 dev 실패만 보고 수행했으며, test는 주요 수정 완료 후 한 번 평가했다. holdout 정답은 공개 패키지에 없고 접근하지 않았다.

## 8. Difficulty별 결과

| 난이도 | 건수 | Decision accuracy | Exact set accuracy |
|---|---:|---:|---:|
| `easy` | 19 | 100.00% | 100.00% |
| `hard` | 48 | 100.00% | 100.00% |
| `medium` | 53 | 100.00% | 100.00% |

## 9. Language style별 결과

| 문체 | 건수 | Decision accuracy | Exact set accuracy |
|---|---:|---:|---:|
| `abbreviated` | 29 | 100.00% | 100.00% |
| `colloquial` | 29 | 100.00% | 100.00% |
| `formal` | 34 | 100.00% | 100.00% |
| `indirect` | 28 | 100.00% | 100.00% |


## 10. 남은 실패 케이스와 원인



잔여 사례는 위 목록과 같다. 동일 통계군 판별과 생략형 followup은 사전 표명, 일반 변경 축, 현행 시계열 여부를 이용하며 query별 예외로 막지 않았다.

## 11. 회귀 및 계약 확인

- Golden v4.1 validator 및 4개 테스트 통과.
- Python compile 통과.
- `tests/TEST_AGENT_FLOW.py` 통과: clarification hard constraint, 사전 ID 기반 API plan, MCP 전달 파라미터 일치 확인.
- 실제 KOSIS 원본 호출 확인: `DT_181Y012`, 2025년 1·2분기 요청에서 2행과 동일 table ID 반환.
- 기존 KOSIS 호출 경로와 `_merge_classifications` 안전장치는 제거하지 않음.
- catalog-only는 item/objL 근거가 없으므로 API를 호출하지 않음.
- clarification UI는 dictionary option만 반환하며 없는 지표를 버튼으로 만들지 않음.

## 12. 추가 권장 작업

1. builder가 없는 현재 거대 dictionary JSON을 재생성 가능한 source pipeline으로 이전한다.
2. followup을 문자열 병합에서 typed query-state reducer로 확장한다.
3. Reranker 문서에 표명뿐 아니라 기간, 주기, sibling 구분 기준을 넣는다.
4. 비공개 holdout은 최종 후보 한 번만 외부 evaluator로 평가한다.

## 13. 데이터 누출·하드코딩 확인

- Golden case ID를 runtime에서 참조하지 않음.
- query 전체 문장과 정답 table ID 매핑을 추가하지 않음.
- holdout answer에 접근하지 않음.
- 평가셋 파일을 runtime lookup으로 읽지 않음.
- 실제 table/item/objL ID는 통계사전과 로컬 메타데이터에서만 사용.
- 실제 수치는 기존 KOSIS/MCP 경로만 사용.
