# 설계와 제작 기준

## 세 계층

| 계층 | 파일 | 공개 |
|---|---|---|
| 계약 | `cases/*.jsonl` | 공개 |
| 숫자 오라클 | `.venv/cache/statbridge-e2e-v1/oracles.json` | 비공개 |
| holdout 정답 | 저장소 밖 | 비공개 |

공개 사례에는 `oracle_sha256`만 있고 값은 없습니다. 값은 `data/tables/*.csv`에서만 추출하며, 연구 PDF 수치·연구 캐시·제품 출력은 정답이 아닙니다.

## Tier

- **A**: 연구 재현명세 3건(`RATE-FULL`, `CREDIT-FULL`, `ESI-FULL`)이 해당 유형의 모든 계열을 덮는 경우. 숫자 채점 가능
- **B**: 계열·기간만 검증된 유형. 숫자 채점 불가
- **C**: 연구에서 기대 계열 출력을 확인하지 못한 유형. `eligible_for_scoring: false`, `unresolved_probe`

Tier는 research `실행판정`이 아니라 "명세가 계열을 덮는가"로 정합니다. C만 `실행판정 != 출력 확인`입니다.

## 문항 구성 (120)

| 묶음 | 수 | 모드 |
|---|---:|---|
| 기본형 36유형 × 그래프/표 | 72 | `query_output` |
| 기간 변형 | 12 | `query_output` |
| 파생 (금리차 1 + 증감률 7) | 8 | `derived` |
| 보고서 초안 | 12 | `report` |
| 후속 대화 | 8 | `follow_up` |
| 편집 | 8 | `edit` |

`report`·`follow_up`·`edit`은 `base_case_id`로 같은 그룹에 묶고 split을 상속합니다. 한 그룹의 모든 사례는 한 split에만 둡니다.

## 정답 규칙

- 기간은 유형별 `bok_periods.csv` 범위 안에서만 생성합니다
- Tier A 오라클은 CSV의 `ITM_ID` + `C1` + 주기로 선택합니다. 같은 표의 연간/월간 행을 섞지 않습니다
- 파생은 `core.calculate`로 독립 계산합니다. 제품 계산기를 호출하지 않습니다
- 질의에는 표 ID(`DT_`)와 `[`를 넣지 않습니다. 소스의 `정확형` 질의는 사용하지 않습니다
- holdout은 dev/test와 다른 기간 창을 쓰는 별도 질의입니다. 같은 질의의 복사가 아닙니다

## 채점

| 모드 | 정량 | 정성 |
|---|---|---|
| `query_output` | 상태, 계열 집합, 기간 집합, Tier A 수치(허용오차 1e-6) | 선택 (`facts`, `clarity`) |
| `derived` | 연산·결과·계열 (어댑터 필요) | 선택 |
| `report` | revision·표시 계열·인용 수치 (모델 필요) | **필수** |
| `follow_up` | 표·주기 보존, 변경 기간 | **필수** |
| `edit` | 편집 결과 상태 | **필수** |

실행 경계: `query_output`·`edit`·`follow_up`은 오프라인에서 실행합니다. `derived`·`report`는 모델이 필요해 `run_model.py`(유료, 승인 전 거부)로 분리합니다. `follow_up`은 `/api/query`가 성공 응답에 `state`를 주지 않아 문맥 전용 질의가 `no_match`가 됩니다(제품 미지원, 기록 대상).

상태: `passed` / `failed` / `pending_review` / `unobserved` / `not_executed` / `excluded`.
정량·정성은 합산하지 않습니다. 정성 검수는 `REVIEW.md`의 0/1/2 rubric을 씁니다.

## 다른 계열과의 경계

- `bok-reproduction/v1`·`v2`: 원본 46개 재현 계열. 이 세트의 120문항과 점수를 합치지 않습니다
- `end-to-end/v1`·`v2`: 간행물 기반 검색 계열. 중복 점수 없음
- `table-discovery/v4.1`: 표 탐색 전용. 계열 선택 지표를 재사용하지 않습니다
- `report_table`, `retrieval`: 별도 실험

## 알려진 한계

- Tier B 25유형은 숫자를 채점하지 않습니다
- `derived`·`report`·`follow_up`·`edit`은 모델 어댑터가 없어 오프라인에서 `not_executed`입니다
- 같은 표의 여러 계열을 한 번에 요청하면 출력 계열 lineage 결합이 모호해 `unobserved`가 될 수 있습니다
- 정성 검수자 2명이 없으면 이중 검수 규칙이 성립하지 않습니다
