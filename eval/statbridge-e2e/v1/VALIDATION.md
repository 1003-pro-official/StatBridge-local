# 제작·검증 기록

2026-10-21 · ai-assisted · 사람 승인 대기 · 공식 성능 아님 · 유료 모델/실시간 KOSIS 호출 0회.

## 만든 것

- `inventory.json`: research 36유형 조인, Tier A 8 / B 25 / C 3
- 공개 120문항 (dev 48 / test 72), holdout 질의 40건, 숫자 오라클 26건
- 실행기: `query_output`·`edit`·`follow_up` 오프라인 / `derived`·`report` 유료 대기
- 검증기·채점기·검수 양식·오라클 검산표·manifest·인계 결정서

## 실제 확인

| 검사 | 관측 결과 |
|---|---|
| `validate.py` | `VALIDATION OK: dev=48 test=72 holdout=40 oracles=26` |
| 신규 테스트 | `14 passed` |
| 오프라인 실행 | 94건 (query_output 78 + edit 8 + follow_up 8), 모델 호출 0 |
| 채점 (main 머지 후) | 정량 통과 `pending_review` **68**, `failed` **0**, `unobserved` 26, `excluded` 6, `not_executed` 20 |
| 정성 검수 | 0건 → `passed` 0건 (실패가 아니라 미검수) |

### 모드별

main 머지(`591f5aca`) 후 재실행 기준입니다.

| 모드 | 실행 | 통과(검수 대기) | 실패 | 미관측 | 미실행 | 제외 |
|---|---:|---:|---:|---:|---:|---:|
| query_output | 78 | 60 | 0 | 18 | 0 | 6 |
| edit | 8 | 8 | 0 | 0 | 0 | 0 |
| follow_up | 8 | 0 | 0 | 8 | 0 | 0 |
| derived | 0 | 0 | 0 | 0 | 8 | 0 |
| report | 0 | 0 | 0 | 0 | 12 | 0 |

## 머지 전 실행에서 관측된 실패 (2026-10-21)

> 아래 1·2번은 main 머지 후 재실행에서 **해소**되었습니다. 3·4번은 그대로 남았습니다.

### 1. 공식 항목명이 파생 라우터를 오탐 (8건)

`SBE-0027/0028`(FIRM-01, 4건), `SBE-0049/0050`(PAY-01, 2건), `SBE-0071/0072`(TRADE-02, 2건)이 `need_details`를 반환했습니다. 응답 사유는 `issue=derived_data`입니다.

질의에 들어간 **공식 통계 항목명**인 `매출액증가율`, `이용금액 합계`, `교역조건지수`가 파생지표 트리거로 잡힌 것입니다. 질의를 바꿔 피하지 않았습니다. 실제 항목명이므로 바꾸면 다른 것을 묻는 셈입니다.

**판정: 제품 라우팅 이슈 후보.** 사례는 유지합니다.

### 2. 출력 계열 lineage 결합 불가 (4건)

같은 표의 여러 계열을 한 요청에 넣으면 `sourceId`(=표 ID)만으로 계열을 유일하게 결합할 수 없습니다. `SBE-0011/0012/0063/0064`입니다.

**판정: 하네스 한계.** 제품 출력은 성공했을 수 있으나 관측을 확정하지 못해 `unobserved`로 남깁니다.

### 3. HTTP 500 (14건) / data_unavailable (3건)

모두 `validation_failed` — "입력·계산 계획·표시 설정 검증에서 중단했습니다." — 이고, `data_unavailable` 3건과 별개입니다. provider를 관련 표·항목의 **모든 분류 조합**으로 넓힌 뒤에도 동일해서, provider 부족이 아니라 제품 검증 단계에서 발생한 것으로 봅니다.

500이 난 그룹은 `CSI-02`(3) · `CSI-03`(2) · `BOP-02`(2) · `BOP-03`(3) · `TRADE-01`(2) · `INF-01`(2)로, 대부분 같은 표의 여러 계열을 한 요청에 넣은 사례입니다. 다만 `INF-01`은 단일 계열이어서 "다계열이면 항상 500"은 아닙니다. 사례별 근본 원인은 확정하지 않았습니다.

### 4. 후속 대화 미지원 (8건)

`/api/query`는 성공 응답에 `state`를 반환하지 않습니다(`need_output_config`에는 `outputSessionId`만 있음). 그래서 이전 턴의 맥락을 서버에 넘길 수 없고, 맥락만 있는 후속 질의는 전부 `no_match`입니다.

**판정: 제품이 문맥 전용 후속 질의를 지원하지 않음.** 사례는 이 기능의 부재를 기록하는 증거로 유지합니다. 기간 변경 자체는 `query_output`의 기간 변형 12건이 이미 측정합니다.

## 2026-10-22 main 머지 후 재실행

`chore: merge main into BOK evaluation branch`(`591f5aca`) 위에서 94건을 다시 실행했습니다.

| 항목 | 머지 전 (`f704861c`) | 머지 후 (`591f5aca`) |
|---|---:|---:|
| 정량 통과(검수 대기) | 57 | **68** |
| 실패 | 8 | **0** |
| 미관측 | 29 | 26 |
| `need_details`(파생 오탐) | 8 | **0** |
| `data_unavailable` | 3 | **0** |
| HTTP 500 | 14 | 14 |
| lineage 결합 불가 | 4 | 4 |
| edit 통과 | 8 | 8 |
| follow_up 미지원 | 8 | 8 |

제품 코드가 바뀐 뒤 실패 8건이 사라졌습니다. **인과를 확정하지는 않습니다.** PR #46의 모델 역할·분류 개선과 같은 시점이라는 관측만 기록합니다. 500 14건과 lineage 4건은 그대로여서 별도 원인입니다.

관측은 머지 후 코드에서 새로 만들었고, 이전 `predictions-final.jsonl`과 합산하지 않습니다.

## 제작 중 수정한 하네스 오류

| 문제 | 수정 |
|---|---|
| CSV의 연간/월간 행이 같은 계열로 섞임 | (항목, 분류, 주기) 키로 분리 |
| provider가 기대 계열만 담아 500 유발 | 관련 (표, 항목)의 모든 분류 조합 포함 (30,776계열, 25MB) |
| `set_transform` 명령 kind 오류 | `STYLE_EDIT` → `DATA_EDIT` |
| `filter_period` 날짜 형식 오류 | 분기 `YYYY0Q`, 월 `YYYYMM` |
| 최근 N개 요청이 가용 기간보다 클 때 | `min(N, 가용 기간)`으로 채점 |

## 남은 일

1. Tier A 오라클 26건 사람 검산 (`oracle_review.py`가 만든 표)
2. HTTP 500 14건의 사례별 원인 확정
3. C단계: 담당자가 `profiles.json` 결정 후 유료 실행 (`HANDOFF.md`)
4. `derived`·`report` 채점, 정성 검수자 2명 확보
5. 비공개 holdout 40건 별도 실행
6. `manifest.py` 재실행 및 결과 반영


## 검증 (2026-10-22)

계획 모드에서 수행한 읽기 전용 검증과, 전환 후 재실행 결과입니다.

| 검사 | 결과 |
|---|---|
| `manifest.py` 재생성 | `product_revision=f704861c` (이전 `15d45957`은 stale) |
| 파일 해시 | 23개 전부 일치 |
| `validate.py` | `VALIDATION OK: dev=48 test=72 holdout=40 oracles=26` |
| 신규 테스트 | `14 passed` |
| 오라클 독립 재추출 | 26건 CSV 대조 **불일치 0** (파생 8건 독립 산식 포함) |
| 누출 검사 | 질의 내 표 ID 0, holdout 정답 필드 0, holdout-공개 질의 중복 0 |
| 분할 검사 | 그룹이 dev/test에 걸친 사례 0 |
| 재현성 | 같은 입력으로 94건 재실행, `execution_status`·`decision`·계열·값·기간·오류 **전부 동일** |
| 재채점 | `pending_review 57 / failed 8 / unobserved 29 / excluded 6 / not_executed 20` (이전과 동일) |
| 기존 계열 영향 | v4.1 validate, bok-reproduction v1 validate 모두 통과 |

재현성 비교에서 `trace`의 시각·trace ID는 실행마다 달라지므로 비교 대상에서 제외했습니다. 관측의 실질 필드는 동일합니다.

### 아직 검증하지 않은 것

- HTTP 500 14건의 사례별 근본 원인
- 사람 정성 검수(검수자 없음), `review_valid` 실제 적용
- C단계 유료 실행, 비공개 holdout 40건
- 프런트엔드 빌드 (이번 변경은 백엔드·평가 파일만)
