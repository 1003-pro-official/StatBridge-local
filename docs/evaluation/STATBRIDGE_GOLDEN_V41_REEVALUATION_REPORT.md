# StatBridge Golden Set v4.1 공개셋 재평가 보고서

- 재평가일: 2026-09-28 (Asia/Seoul)
- 대상 코드: `StatBridge1/StatBridge-official` 현재 작업본
- 평가 입력: `golden-set-v4.1-public/cases_labeled.jsonl`
- 총 평가 건수: 120건 (`dev` 50건, `test` 70건)
- 새 원본 결과: `golden_v41_reevaluation_results.json`

## 1. 재평가 방법

기존 최종 결과 JSON을 재사용하지 않고 아래 명령으로 120건을 처음부터 다시 실행했다.

```powershell
python StatBridge-official\tools\evaluate_golden_v41.py `
  --dataset golden-set-v4.1-public\cases_labeled.jsonl `
  --output golden_v41_reevaluation_results.json
```

`holdout_queries.jsonl`은 정답이 없으므로 점수 계산과 정답 추정에 사용하지 않았다. 결과 해석에서는 다음 두 층을 분리한다.

1. **원시 후보 검색 지표**: 일반 `rank()`가 반환한 Top-K 안에 정답 표가 있는지 측정한다.
2. **최종 실행 결과**: clarify/no-match 판단, multi-series 분해, 동일 통계군 sibling 선택, followup 상태 복원까지 적용한 뒤 최종 table ID 집합을 측정한다.

## 2. 평가 구성

| 유형 | 건수 |
|---|---:|
| single | 48 |
| multi | 16 |
| clarify | 16 |
| no_match | 12 |
| catalog_only | 4 |
| followup | 24 |
| **합계** | **120** |

## 3. 원시 후보 검색 성능

| 지표 | 재평가 결과 |
|---|---:|
| Recall@1 | 89.13% |
| Recall@3 | 91.30% |
| Recall@5 | 92.39% |
| MRR | 0.9049 |
| Top-1 Accuracy | 89.13% |

이 수치는 전체 StatBridge 최종 응답 정확도가 아니다. 특히 생략형 followup은 현재 발화만 `rank()`에 넣으면 후보가 없거나 넓게 검색될 수 있으며, 실제 실행에서는 이전 상태를 적용한 `rank_followup()`이 최종 표를 결정한다.

## 4. 최종 실행 결과

| 지표 | 재평가 결과 |
|---|---:|
| 최종 status 정확도 | **120/120 (100%)** |
| 최종 table-set Exact Match | **120/120 (100%)** |
| multi-table Exact Set Match | **16/16 (100%)** |
| multi-table Precision | **100%** |
| multi-table Recall | **100%** |
| multi-table F1 | **100%** |
| clarify decision accuracy | **16/16 (100%)** |
| no_match decision accuracy | **12/12 (100%)** |
| catalog_only decision accuracy | **4/4 (100%)** |
| followup accuracy | **24/24 (100%)** |

### Split별 최종 정확도

| Split | 건수 | Decision | Exact Set |
|---|---:|---:|---:|
| dev | 50 | 100% | 100% |
| test | 70 | 100% | 100% |

### 난이도별 최종 정확도

| 난이도 | 건수 | Decision | Exact Set |
|---|---:|---:|---:|
| easy | 19 | 100% | 100% |
| medium | 53 | 100% | 100% |
| hard | 48 | 100% | 100% |

### 문체별 최종 정확도

| 문체 | 건수 | Decision | Exact Set |
|---|---:|---:|---:|
| abbreviated | 29 | 100% | 100% |
| colloquial | 29 | 100% | 100% |
| formal | 34 | 100% | 100% |
| indirect | 28 | 100% | 100% |

## 5. 원시 후보와 최종 결과가 다른 10건

아래 10건은 원시 `rank()`의 Top-K 지표에는 실패로 기록되지만, 최종 상태 복원·복수표 결합 결과는 정답과 일치한다.

| ID | 원시 후보 상태 | Gold | 최종 출력 |
|---|---|---|---|
| GS4-0139 | Recall@5 밖 | DT_281Y002 | DT_281Y002 |
| GS4-0144 | Recall@5 밖 | DT_404Y016 | DT_404Y016 |
| GS4-0121 | Gold 원시 4위 | DT_181Y012 | DT_181Y012 |
| GS4-0130 | Recall@5 밖 | DT_403Y002, DT_403Y004 | DT_403Y002, DT_403Y004 |
| GS4-0131 | Recall@5 밖 | DT_405Y006 | DT_405Y006 |
| GS4-0132 | Recall@5 밖 | DT_405Y006, DT_405Y007 | DT_405Y006, DT_405Y007 |
| GS4-0141 | Recall@5 밖 | DT_282Y005 | DT_282Y005 |
| GS4-0147 | Recall@5 밖 | DT_513Y001 | DT_513Y001 |
| GS4-0148 | Gold 원시 2위 | DT_602Y002 | DT_602Y002 |
| GS4-0149 | Gold 원시 2위 | DT_181Y002 | DT_181Y002 |

따라서 `failure_counts = {C: 7, D: 3}`은 최종 실패 10건을 뜻하지 않는다. 이는 원시 단일 검색 후보의 순위 진단값이며, 최종 Exact Set 실패 파일은 0건이다.

## 6. 결론과 제한

- 현재 공개된 labeled 120건에서는 최종 판단과 최종 table ID 집합이 모두 정답과 일치했다.
- 원시 후보 검색은 Recall@1 89.13%, Recall@5 92.39%로 100%가 아니며, 최종 정확도는 후속 상태 복원과 복수표 결합 로직을 포함했을 때의 결과다.
- 공개 dev/test에 대한 결과이므로 새로운 실사용 문장이나 비공개 holdout에서도 100%라고 주장할 수 없다.
- `holdout_queries.jsonl`에는 정답을 생성하거나 추정하지 않았다.
- 평가 ID나 전체 문장을 runtime 정답 매핑으로 사용하는 코드는 추가하지 않았다.
