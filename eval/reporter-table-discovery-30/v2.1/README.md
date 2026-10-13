# 기자 질의 통계표 탐색 골든셋 v2.1 (목표 200문항)

v2의 30문항과 단계별 정답 형식을 그대로 유지하고, 한국은행 보고서의 그림·표 주제를 출처로 새 문항을 증강한 공개 개발용 골든셋입니다.

- 기준일: 2026-10-13
- 스키마: `reporter200-discovery-2.1` (v2에서 그대로 옮긴 30문항은 `reporter30-discovery-2` 유지)
- 문항: 200개 = v2 원본 30 + 증강 170 (`resolved` 140, `no_match` 53, `need_clarification` 7)
- 증강 170의 구성: 단일 계열 28 / 한 표 복수 계열 80 / 여러 표 복수 계열 11, 표 96개
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
| `scripts/specs/batch*.json` | 작성 배치별 문항 스펙(질문·상태·표·분류값 이름·출처). 생성기의 입력 |
| `scripts/validate.py` | 카탈로그 코드·기간·API 파라미터·v2 원본 보존·research 출처를 확인하는 검증기 |
| `tests/test_validate.py` | 분류 코드 오류, 계열 누락, v2 본문 변조, 출처 해시·행 불일치를 거부하는 회귀 테스트 |

## 단계별 골드

v2와 동일하게 `query_interpretation`, `table_discovery`, `item_selection`, `classification_and_plan`, `resolution`, `post_discovery`를 기록하고, 증강 문항에는 `research_references`를 추가합니다. 값은 런타임 예측 로그가 아니라 카탈로그 메타데이터로 작성한 규범적 기대 정답입니다.

## 범위와 한계

- 평가 범위는 통계표 탐색까지입니다. KOSIS 수치 호출, 로컬 CSV, 그래프 출력, 해석 문장은 `excluded_from_scoring`입니다.
- 자동 검증 통과는 골드의 사람 승인을 뜻하지 않으며 모델 성능 점수로 해석하지 않습니다.
- `v1`, `v2`, `v3`, `v3-four-tables`, `table-discovery/`, `end-to-end/`, `statbridge-golden/`과 버전·점수를 혼용하지 않습니다.
- 비공개 평가 저장소와 holdout 정답은 포함하지 않습니다.

## 검수 기록

- 170문항을 전수 육안 검수해 질의와 표·계열 대응을 확인했다. 발견한 결함 2건을 고쳤다: `REPORTER30-V2.1-142`는 질의에 없는 `국민총처분가능소득` 계열이 정답에 있어 질의를 정답과 맞췄고, `REPORTER30-V2.1-090`은 `REPORTER30-V2.1-040`과 표·계열·문구가 사실상 같은 중복이어서 CD·RP 금리 비교로 바꿨다.
- 검증기 통과는 골드의 사람 승인이 아니다. 자동 검사는 구조·코드·해시만 확인하고 질의의 의미와 계열 선택의 타당성은 검사하지 않는다.

## 한계

- `seasonal_adjustment` 역질문 그룹은 카탈로그의 `trigger_terms`가 M2 관련어로 되어 있어 실질 GDP 질문으로는 런타임이 이 역질문을 띄우지 않을 수 있다. 골드 그룹·선택지는 카탈로그와 일치한다.
- 증강 170문항은 research 결과물ID 166개를 참조한다(4개는 서로 다른 두 문항이 같은 그림·표를 출처로 씀).
- `no_match` 45건의 부재 판정은 공개 카탈로그 메타데이터 검색에 근거한다. KOSIS 실시간 호출로 재확인하지 않았고, 시산 지표가 정기 통계표로 편입되면 판정이 바뀔 수 있다.

## 검증

```bash
python3 eval/reporter-table-discovery-30/v2.1/scripts/build.py
python3 eval/reporter-table-discovery-30/v2.1/scripts/validate.py
python3 -m pytest -q eval/reporter-table-discovery-30/v2.1/tests
```
