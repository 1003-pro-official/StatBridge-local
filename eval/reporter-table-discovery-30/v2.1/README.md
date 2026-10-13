# 기자 질의 통계표 탐색 골든셋 v2.1 (목표 200문항)

v2의 30문항과 단계별 정답 형식을 그대로 유지하고, 한국은행 보고서의 그림·표 주제를 출처로 새 문항을 증강하는 공개 개발용 골든셋입니다. 목표는 200문항이며 현재는 1배치 25문항이 반영되어 **55문항**입니다.

- 기준일: 2026-10-13
- 스키마: `reporter200-discovery-2.1` (v2에서 그대로 옮긴 30문항은 `reporter30-discovery-2` 유지)
- 문항: 55개 = v2 원본 30 + 증강 25 (`resolved` 39, `no_match` 14, `need_clarification` 2)
- 정답 근거: 한국은행 KOSIS 카탈로그(`org_id=301`) 349개 표 메타데이터
- 검수 상태: `ai-assisted`, 사람 승인 대기 (`human_approved=false`)
- 모든 문항은 공개 `dev`이며 블라인드 holdout이 아닙니다.

## 증강 기준

- v2 원본 30문항은 바이트 수준이 아니라 **JSON 내용 그대로** 옮깁니다. `schema_version`만 v2 값이 남습니다. 검증기가 v2 파일과 대조해 본문 변경을 거부합니다.
- 신규 문항은 `research/그림표-분석/`의 보고서 그림·표 주제에서 착안합니다. 출처는 `research_references`에 경로·행·제목·결과물 ID·SHA256으로 기록하고, **research 본문은 정답 근거가 아닙니다**. 표 ID·항목·분류 코드는 카탈로그에서만 가져옵니다.
- 연구 문서의 `추정`·`불명` 필드는 질문 소재로도 정답 근거로도 쓰지 않습니다.
- 기간 정책과 판정 규칙은 v2와 동일합니다. 명시 기간은 포괄적 KOSIS 기간으로 변환하고, 기간 미지정 문항은 런타임 계획을 기록한 뒤 API `need_period` 후속을 기대합니다.
- 표 ID 집합과 계열 코드 조합은 순서 없이 정확히 일치해야 하며, 누락·추가 계열은 실패입니다.

## 파일

| 파일 | 내용 |
|---|---|
| `statbridge-reporter200.jsonl` | 55문항(증강분 포함), 질의·해석 슬롯·단계별 정답·출처 |
| `statbridge-reporter200.md` | 문항별 질문·상태·정답 표 요약 |
| `dataset_manifest.json` | 버전, 상태·스키마별 집계, dataset·catalog·research SHA256 |
| `scripts/build.py` | 문항 스펙에서 정답 JSONL·요약·manifest를 생성. 런타임 예측을 읽지 않음 |
| `scripts/validate.py` | 카탈로그 코드·기간·API 파라미터·v2 원본 보존·research 출처를 확인하는 검증기 |
| `tests/test_validate.py` | 분류 코드 오류, 계열 누락, v2 본문 변조, 출처 해시·행 불일치를 거부하는 회귀 테스트 |

## 단계별 골드

v2와 동일하게 `query_interpretation`, `table_discovery`, `item_selection`, `classification_and_plan`, `resolution`, `post_discovery`를 기록하고, 증강 문항에는 `research_references`를 추가합니다. 값은 런타임 예측 로그가 아니라 카탈로그 메타데이터로 작성한 규범적 기대 정답입니다.

## 범위와 한계

- 평가 범위는 통계표 탐색까지입니다. KOSIS 수치 호출, 로컬 CSV, 그래프 출력, 해석 문장은 `excluded_from_scoring`입니다.
- 자동 검증 통과는 골드의 사람 승인을 뜻하지 않으며 모델 성능 점수로 해석하지 않습니다.
- `v1`, `v2`, `v3`, `v3-four-tables`, `table-discovery/`, `end-to-end/`, `statbridge-golden/`과 버전·점수를 혼용하지 않습니다.
- 비공개 평가 저장소와 holdout 정답은 포함하지 않습니다.

## 진행 상태

증강은 상태 분포를 v2 비율(resolved 약 70%, no_match 약 27%, need_clarification 약 3%)로 유지합니다. 목표 200문항 = v2 30 + 증강 170(단수 28 / 한 표 복수 79 / 여러 표 복수 11 중 resolved 119, no_match 45, need_clarification 6). 현재 1배치 25문항이 반영되었고 나머지 145문항은 같은 방식으로 이어서 작성합니다.

## 검증

```bash
python3 eval/reporter-table-discovery-30/v2.1/scripts/build.py
python3 eval/reporter-table-discovery-30/v2.1/scripts/validate.py
python3 -m pytest -q eval/reporter-table-discovery-30/v2.1/tests
```
