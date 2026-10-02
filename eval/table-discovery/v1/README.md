# ClaBi KOSIS Golden Set v1 Pilot

상태: **초안 — 사례별 정답 승인 0/150**. ClaBi에서 이관한 별도 검토용 버전입니다. 기계 생성 후보와 기존 60건 초안은 정답으로 간주하지 않습니다.

## 구성과 분할

`cases.jsonl`에는 사례마다 주 유형 하나, 보조 태그, 원문 대화, 전체 파이프라인 기대 결과, 후보 표의 초안 관련도(0–3), 메타정보 근거, 사람 검토 상태를 기록합니다. 같은 원질의의 후속 답변은 하나의 사례 안에 실행 경로로 포함합니다.

| 주 유형 | 건수 |
|---|---:|
| 명확한 단일 표 질의 | 30 |
| 일상어·별칭 질의 | 25 |
| 모호성·역질문 질의 | 20 |
| 복수 지표·복수 표 질의 | 20 |
| 기간·주기·계열·대상 조건 질의 | 20 |
| 무결과·범위 밖 질의 | 15 |
| 대화 맥락·후속 질의 | 20 |
| **합계** | **150** |

Split은 `dev` 30, `validation` 30, `locked_test` 90입니다. 이 크기는 첫 파일럿의 라벨링 부담과 오류 유형 점검을 위한 선택이며, 작은 모델 간 성능 차이를 확정할 통계적 표본 수가 아닙니다.

## 파일

- `cases.jsonl` — UTF-8 JSONL 정본 초안(150행)
- `schema.json` — 사례 레코드 JSON Schema
- `review.xlsx` — `안내`와 `사례 검토` 시트. A:N은 초안·근거, O:R은 검토 입력 칸이며 파이프라인 라벨을 모두 표시합니다.
- `catalog_manifest.json` — 카탈로그 전체 목록, 소스 기준일·해시, 커버리지, 검증 상태
- `coverage.csv` — 상위 분류 경로와 유형×split별 커버리지
- `kosis_metadata_export.json` — 후보 57개 표의 KOSIS API 주기·항목/분류 응답 원본
- `scripts/manage_golden_set.py` — 구조 검증, Excel 생성, API 재수집, Excel 검토 입력 반영

기존 파일에서 재사용한 자료는 `eval/goldenset/*.json`의 원문 질의 초안과 `data/kosis/hankook_tables.json`, `src/backend/data_full/collection/table_summary.csv`, `src/backend/data_full/tables/*.csv`의 카탈로그·메타정보입니다. 기존 정답 필드는 그대로 승인값으로 복사하지 않았습니다.

## KOSIS 및 카탈로그 검증 범위

- 카탈로그 스냅샷: `data/kosis/hankook_tables.json`, 349개 표, 수집일 2026-09-14.
- 로컬 표 데이터: CSV 347개. 카탈로그 전체와 KOSIS API 결과가 같은 범위라고 가정하지 않습니다.
- KOSIS Open API: 프로젝트의 `KosisClient`로 후보 59개에 대해 `getMeta(PRD)`와 `getMeta(ITM)`를 조회했고, 59개 모두 응답을 받았습니다(2026-09-23 UTC). 주기·수록시점·항목/분류 일부를 기록했습니다.
- 조회한 API 종류는 단위, 주석, 전체 계열 정의를 주지 않으므로 해당 값은 미검증으로 남겼습니다. 59개 후보 중 6개는 로컬 CSV 단위도 기록되지 않았고, 주석/계열 정의는 59개 모두 미확인입니다.
- 모든 후보 점수와 라벨은 `review_required`입니다. API 메타정보 성공은 표가 질의에 적합하다는 뜻이 아닙니다.
- `NO_MATCH`는 한국은행 프로젝트 카탈로그 349행을 대상으로 한 초안 판정입니다. 현재 KOSIS 전체 카탈로그 검색은 실행하지 않았으므로 실제 탐색 조건과 범위를 사례별 기록과 대조해 사람이 확인해야 합니다.
- snapshot/API 기간이 맞지 않거나 오래된 계열이면 대안을 임의로 정답 처리하지 말고 메모와 `needs_adjudication`으로 넘기세요.

## 검토 절차

1. `review.xlsx`의 `사례 검토` 시트에서 원문·맥락, 슬롯, 모호성/역질문, 전략, 도구 계획, 검색 후보, 메타정보와 증거를 확인합니다. `안내` 시트에 열 정의와 결정 기준도 있습니다.
2. `검토 결정`을 `승인`, `수정`, `보류`, `제외` 중 하나로 입력합니다. `수정`이면 수정 라벨/정답과 근거를 적고, 승인할 표 ID 또는 `NO_MATCH`를 기록합니다. `보류`는 판단 근거/추가 확인 사항을 메모합니다.
3. 검토 입력을 JSONL에 반영하려면 저장된 Excel 파일을 사용해 실행합니다:

   ```bash
   python3 eval/table-discovery/v1/scripts/manage_golden_set.py import-review eval/table-discovery/v1/review.xlsx
   ```

   이 명령은 `review` 객체에 검토자 입력만 기록합니다. `gold`, `annotation.review_status`를 바꾸지 않고 승인도 자동으로 처리하지 않습니다.
4. 가져오기 후 JSONL의 `review` 입력을 확인합니다. 정답을 승인하려면 사람이 수정 내용을 `gold`에 반영하고 `review.decision`을 `승인`으로 확정한 뒤, 표 ID 또는 `NO_MATCH`를 기록하고 `annotation.review_status`를 `approved`로 명시 변경합니다. `수정`은 수정안을 `gold`에 적용하고 재검토하기 전까지 승인 상태가 아닙니다. `보류`는 `needs_adjudication`, `제외`는 `excluded`로 기록하며 둘 다 점수 산정에서 제외합니다. `import-review`는 어떤 상태도 자동 변경하지 않습니다.

5. Excel을 다시 생성해도 O:R 검토 입력은 현재 JSONL `review` 값에서 복원됩니다. 다만 Excel에서 입력한 값은 `import-review` 실행 전까지 JSONL에 저장되지 않습니다. 사례별로 최종 라벨을 확정한 뒤 `validate`와 `manifest`를 다시 실행하세요.

### Excel → JSONL 필드 연결

| Excel 열 | JSONL 경로 | 반영 규칙 |
|---|---|---|
| `case_id` | `case_id` | 키로 사례를 찾습니다. 편집하지 않습니다. |
| `검토 결정` | `review.decision` | 입력 그대로 저장합니다. final 승인 상태는 바꾸지 않습니다. |
| `승인할 통계표 ID` | `review.approved_table_ids` | 쉼표 입력도 문자열 그대로 기록합니다. 무결과는 `NO_MATCH`. 사람이 정본 수정 시 후보 및 근거와 대조합니다. |
| `수정 라벨 또는 정답` | `review.edited_gold` | JSON 객체 또는 설명을 문자열로 보존합니다. 자동 병합하지 않습니다. |
| `검토 메모` | `review.review_notes` | 문자열 그대로 기록합니다. |
| 나머지 초안 열 | `gold.*`, `conversation`, `annotation.*` | Excel에서 편집된 초안은 자동 반영하지 않습니다. 확정할 변경은 사람이 JSONL에 반영합니다. |

## 재생성·검사

JSONL 검증(파싱·150건·중복 ID·유형/split 배분·후보 ID 연결·검토 상태):

```bash
python3 eval/table-discovery/v1/scripts/manage_golden_set.py validate
```

카탈로그 manifest와 커버리지 표 갱신 및 Excel 검토표 재생성:

```bash
python3 eval/table-discovery/v1/scripts/manage_golden_set.py manifest
python3 eval/table-discovery/v1/scripts/manage_golden_set.py workbook
```

KOSIS 메타정보를 새로 조회하려면 저장소 루트에서 프로젝트 의존성이 설치된 Python을 사용합니다:

```bash
PYTHONPATH=src/backend python3 eval/table-discovery/v1/scripts/manage_golden_set.py refresh-kosis
python3 eval/table-discovery/v1/scripts/manage_golden_set.py enrich-kosis
python3 eval/table-discovery/v1/scripts/manage_golden_set.py manifest
```

`refresh-kosis`는 표 ID별 API 원문 응답만 다시 내보냅니다. `enrich-kosis`가 JSONL에 메타정보 요약·근거를 붙입니다. API 키 값은 로그나 산출물에 기록하지 않습니다. `python-dotenv` 등 프로젝트 의존성이 없다면 `src/backend/requirements.txt`를 설치한 뒤 실행합니다.
