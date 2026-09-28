# StatBridge Golden Set v4.1 (150-case benchmark, repaired)

## 목적

StatBridge의 **자연어 질의 → 통계표 탐색(table discovery)** 을 자동 평가하기 위한 벤치마크다.
이 버전은 v4의 150개 케이스를 최대한 보존하면서 구조/라벨 오류와 평가 누수를 교정했다.

## 가장 중요한 변경

1. **층화 split**: dev 50 / test 70 / holdout 30 각각에 모든 케이스 유형이 섞이도록 재배치.
2. **진짜 holdout 분리**: 공개 패키지에는 `holdout_queries.jsonl`만 있으며 정답은 별도 private evaluator 패키지에만 존재.
3. **기간 슬롯 교정**: 질문의 연도와 맞지 않던 다수 `slots.period`를 실제 질문 기준으로 수정.
4. **문체/난이도 분리**: type과 `language_style`/`difficulty`가 1:1로 묶이지 않도록 보정.
5. **item ID 보강**: evidence에서 선택 표별 item ID가 정확히 하나로 검증되는 경우 `expected_items.item_by_table`에 기록.
6. **dimension Gold는 만들지 않음**: 원본 근거가 부족하므로 `dimension_values_status=not_labeled`로 명시.
7. **human approval 과장 제거**: review는 `machine_reviewed`, `human_approved=false`로 기록.
8. **hard negative 개선**: 명확한 sibling 통계군은 semantic family 기반으로 먼저 지정하고 기존 catalog-neighbor를 보조로 유지.

## 파일

- `dev.jsonl`: 50개, 정답 포함
- `test.jsonl`: 70개, 정답 포함
- `cases_labeled.jsonl`: dev+test 120개
- `holdout_queries.jsonl`: 30개, **정답 미포함**
- `review/review_sample_36.csv`: 선택적 독립 표본검수용
- `scripts/validate_v41.py`: self-contained 구조/누수/분포/기간 검증
- `scripts/score_labeled.py`: dev/test prediction 평가
- `tests/test_v41.py`: validator 핵심 테스트

## split 분포

| type | dev | test | holdout | total |
|---|---:|---:|---:|---:|
| single | 20 | 28 | 12 | 60 |
| multi | 7 | 9 | 4 | 20 |
| clarify | 7 | 9 | 4 | 20 |
| no_match | 5 | 7 | 3 | 15 |
| catalog_only | 2 | 2 | 1 | 5 |
| followup | 9 | 15 | 6 | 30 |
| **total** | **50** | **70** | **30** | **150** |

## 평가 범위

이 v4.1로 공식적으로 평가할 수 있는 범위:

- expected status (`select`, `clarify`, `no_match`, `catalog_only`)
- single table exact accuracy
- multi table exact set match / set precision / recall / F1
- clarification decision accuracy
- no-match / catalog-only decision accuracy
- follow-up context table selection
- Retrieval Recall@K / MRR (시스템이 ranked candidates를 출력하는 경우)
- **item ID accuracy: 선택 표가 evidence에서 단일 item ID로 검증된 케이스에 한해 가능**

아직 평가할 수 없는 범위:

- objL1..objL8 분류값 exact accuracy (`dimension_values` Gold가 아직 없음)
- 실제 KOSIS 수치 일치율
- normalize / merge / calculate 정확도

따라서 이 버전의 이름은 **Table Discovery Benchmark**가 정확하다. StatBridge 전체 E2E 골든셋으로 과장해서 사용하지 않는다.

## holdout 운용 규칙

`golden-set-v4.1-private-evaluator.zip`은 개발 프로젝트, Codex, Agent 프롬프트, 검색 인덱스가 접근할 수 있는 위치에 두지 않는다.
개발 중에는 dev/test만 사용하고, holdout은 최종 후보 버전에서 제한적으로 평가한다.

## 사람 검수에 대한 상태

150건 전체의 인간 승인을 주장하지 않는다. 이 패키지는 자동 구조검증과 독립적인 기계 검토를 거친 **평가 준비본**이다.
공식 대외 KPI로 고정하기 전에는 `review_sample_36.csv`처럼 층화 표본을 별도 사람이 검수하는 것을 권장한다.
