# ClaBi KOSIS Golden Set v2

상태: **구조 개선 초안 — 정답 승인 0/150**. 이 폴더는 [`../v1/`](../v1/README.md) 산출물을 보존한 채 별도 생성한 v2입니다. v1 값은 질의·분할 및 검토 후보 생성의 출발점일 뿐 정답 근거로 승계하지 않았습니다. 전체 사례는 `review_required`이며 자동 생성·변환만으로 정답이 승인되지 않습니다.

## 구성

| 유형 | 건수 |
|---|---:|
| 명확한 단일 표 질의 | 30 |
| 일상어·별칭 질의 | 25 |
| 모호성·역질문 질의 | 20 |
| 복수 지표·복수 표 질의 | 20 |
| 기간·주기·계열·대상 조건 질의 | 20 |
| 무결과·범위 밖 질의 | 15 |
| 대화 맥락·후속 질의 | 20 |
| **합계** | **150** |

Split은 `dev` 30 / `validation` 30 / `locked_test` 90입니다. `leakage_group`이 split 간에 갈라지지 않도록 고정했습니다. `plan_validation_cases.jsonl`은 H 단계의 도구명·필수 인자·허용 인자·순서·질문 차단을 검증하는 12개 컴포넌트 fixture로, 150개 질의 사례 수에는 포함하지 않습니다.

## 산출물

- `cases.jsonl`: UTF-8 정본 초안. A~I 및 표 탐색 단계 라벨을 포함합니다.
- `plan_validation_cases.jsonl`: 독립 계획 검증 fixture.
- `review.xlsx`: 안내 시트와 사례 검토 시트. 의도/슬롯, 사용자 확인, 전략, 도구 계획, 계획 검증, 후보 메타정보와 handoff를 모두 표시합니다.
- `schema.json`: v2 레코드 구조.
- `catalog_manifest.json`, `coverage.csv`: 유형·split·상태·카탈로그 경로·KOSIS 메타정보 확인 범위.
- `kosis_metadata_export.json`: 후보 ID만 대상으로 한 프로젝트 `KosisClient` API 원문 응답. API 키는 포함하지 않습니다.
- `scripts/build_v2.py`: v1 초안에서 별도 v2 초안 생성.
- `scripts/manage_v2.py`: 구조 검증, workbook 생성, KOSIS 메타정보 내보내기/반영, Excel 검토 입력 반영, manifest 갱신.

## 구조 변경

- 원문 마지막 질의와 앞선 대화 턴을 분리하고, 후속 질의에서 유지할 맥락과 덮어쓸 조건을 별도 필드로 기록합니다. 자동 추출값은 검토 대상입니다.
- 상대 기간은 `type: relative`, 기간 길이, `reference_date: 2026-09-23`, 원문 표현으로 보존합니다. 실제 조회 종료시점은 표 메타정보에서 기준일 이전 최신 관측시점으로 확인합니다. v1의 `202108` 같은 단일 시작값을 승인값으로 취급하지 않습니다.
- 비적용 목록은 `[]`, 미지정 scalar는 `null`, API/스냅샷에서 확인할 수 없는 메타정보는 `null`과 출처 상태로 표시합니다. gold 내부에 문자열 `N/A`를 센티널로 사용하지 않습니다.
- 개념 후보와 원문 질의를 분리하고, 별칭 후보는 근거 및 검토 상태를 함께 둡니다. 기존 단일 후보는 허용 정답으로 확정되지 않았습니다.
- 역질문 여부, 이미 알려진 필드를 다시 묻지 말아야 하는 조건, 각 답변 뒤의 계획 준비 상태를 저장합니다.
- 데이터 전략은 유형·필수 메타정보 검사·병합 여부·계산 여부로 구조화합니다.
- 도구 계획은 동결된 `schemas/mcp_tools.json`의 도구명과 필수 인자를 반영합니다. 구현된 `allowed_tools`, 메타정보·조건 확인 뒤에만 허용되는 `conditionally_allowed_tools`(현재 `fetch_data`), 아직 실행할 수 없는 `planned_tools`(`merge_datasets`, `render_chart`)를 분리하고 도구 순서와 차단 조건을 기록합니다.
- `plan_validation`과 `handoff`를 사례마다 추가합니다. 계획 검증 전용 실패 예제는 별도 fixture로 둡니다.

## 카탈로그·KOSIS 검증 범위

- 재사용 카탈로그: `data/kosis/hankook_tables.json`, 349개 표, 기준 스냅샷 2026-09-14. 로컬 표 요약/CSV 및 `schemas/mcp_tools.json`도 재사용했습니다.
- v1의 KOSIS API 메타정보 내보내기 59개 표분을 입력 자료로 복사하고, v2 후보 총 68개 ID를 프로젝트 `KosisClient`의 `getMeta(PRD)`·`getMeta(ITM)`로 확인했습니다. 압축하지 않은 API 원문은 `kosis_metadata_export.json`에, 사례별 요약은 JSONL에 둡니다. 조회 내보내기는 표 ID 후보만 대상으로 하며 전체 KOSIS 카탈로그 검색이 아닙니다.
- 주기·기간·항목/분류는 조회 응답 및 로컬 요약을 대조합니다. API 엔드포인트로 확인하지 않은 주석과 완전한 계열 정의는 미검증으로 남겼습니다. 일부 로컬 단위·항목 상세가 없는 경우 빈 결과로 꾸미지 않고 `null` 및 출처 상태를 기록합니다.
- v1의 15개 `NO_MATCH`는 승인 판정이 아닙니다. 후보 생성기는 349행 카탈로그 제목·경로·로컬 요약에서 질의별 검색어의 문자 일치 후보를 최대 3개 제안합니다. 이 후보는 검색기의 실제 결과가 아니며 관련성도 검증되지 않았습니다. 문자가 겹치지 않아 후보가 없는 경우도 있으며, 그 행의 빈 후보는 “카탈로그 검색 완료”를 뜻하지 않습니다. 전체 KOSIS 검색도 수행하지 않았습니다. 모든 해당 사례는 `review_required`입니다.
- 표 ID와 이름이 맞더라도 항목/분류·주기·단위·수록기간·주석·계열 정의를 질의 조건과 비교한 사람 승인 전에는 최종 정답으로 사용하지 않습니다.

## 사람 검토 방법

1. Excel `안내` 시트를 읽고 `사례 검토` 시트에서 원문부터 handoff까지 확인합니다. 초안은 A:R, 검토 입력은 S:W입니다.
2. `검토 결정`은 `승인`, `수정`, `보류`, `제외` 중 하나로 입력합니다. 승인 표 ID는 복수일 때 쉼표로 구분하고, 실제 무결과로 확인한 경우만 `NO_MATCH`를 입력합니다. 수정 시 정본에 적용할 JSON/필드 변경과 검토 근거를 적습니다.
3. Excel을 저장한 후 저장소 루트에서 실행합니다:

   ```bash
   python3 eval/table-discovery/v2/scripts/manage_v2.py import-review eval/table-discovery/v2/review.xlsx
   ```

   검토 입력은 `review` 필드에만 저장합니다. `gold`와 `annotation.review_status`는 자동 변경되지 않습니다.

4. 정답을 최종 승인할 때는 사람이 수정 사항을 `gold`에 적용하고, 근거·검토자·검토일을 기록한 후에만 `review.decision = "승인"` 및 `annotation.review_status = "approved"`로 확정합니다. 보류는 `needs_adjudication`, 제외는 `excluded`로 사람만 변경합니다. 승인되지 않은 사례는 채점에서 제외합니다.
5. 결과를 확인합니다:

   ```bash
   python3 eval/table-discovery/v2/scripts/manage_v2.py validate
   python3 eval/table-discovery/v2/scripts/manage_v2.py manifest
   ```

## 재생성 및 API 재조회

`build_v2.py`는 사람이 편집한 v2 JSONL을 덮지 않도록 기본적으로 기존 파일이 있으면 중단합니다. `--force`는 아직 검토 입력이 없는 새 초안을 의도적으로 다시 만들 때만 사용하세요.

KOSIS 재조회는 프로젝트 의존성이 설치된 Python으로 실행합니다. `.env`에는 API 키가 필요하지만 키 값은 출력하거나 JSON 내보내기에 쓰지 않습니다.

```bash
python3 -m pip install -r src/backend/requirements.txt
PYTHONPATH=src/backend python3 eval/table-discovery/v2/scripts/manage_v2.py refresh-kosis
```

`refresh-kosis`는 후보 표 ID 전체에 대해 PRD/ITM 메타정보를 다시 조회하며, 모든 KOSIS 통계표 검색을 대신하지 않습니다.
