# 기자 질의 기반 통계표 탐색 골든셋 v2

한국은행 보고서를 취재하는 기자의 자연어 질문 30건을 대상으로, 질문 해석부터 한국은행 KOSIS 통계표·항목·분류값 선택과 API 조회 계획까지를 단계별로 평가하는 공개 개발용 골든셋입니다.

- 기준일: 2026-10-08
- 스키마: `reporter30-discovery-2`
- 문항: 30개 (`resolved` 21, `no_match` 8, `need_clarification` 1)
- 정답 계열: 39개, 통계표: 17개
- 데이터 범위: 한국은행 KOSIS 카탈로그(`org_id=301`)
- 검수 상태: `ai-assisted`, 사람 승인 대기 (`human_approved=false`)
- 모든 문항은 공개 `dev`이며 블라인드 holdout이 아닙니다.

## 파일

| 파일 | 내용 |
|---|---|
| `statbridge-reporter30.jsonl` | 질의, 해석 슬롯, 단계별 정답값과 상태 |
| `statbridge-reporter30.md` | 문항별 질문 및 정답 요약 |
| `dataset_manifest.json` | 버전, 상태별 사례 수, SHA256, 기간 정책 |
| `scripts/validate.py` | 코드·계획·상태·해시를 확인하는 오프라인 검증기 |
| `tests/test_validate.py` | 코드 오류, 계열 누락, 기간 없는 사례의 응답 경계 테스트 |

## 단계별 골드

각 문항의 `workflow_gold`에는 다음을 둡니다.

1. `query_interpretation`: 지표, 대상, 측정값, 비교 여부, 주기, 명시 기간
2. `table_discovery`: 기대 정답 통계표 ID(`expected_table_ids`)와 선택 표 ID·표 이름
3. `item_selection`: 통계표별 KOSIS 항목 ID
4. `classification_and_plan`: 계열별 분류 코드·표시 이름, 기관, 주기, 기간, 정확한 API 파라미터
5. `resolution`: 기대 Agent 상태, 사용자 응답 경계 상태, 역질문 여부 및 사례별 계열·표 수
6. `post_discovery`: 수치 실행 전 UI의 기간 확인 또는 확인 질문 상태

이 상태와 선택값은 실제 런타임 예측 로그가 아니라 채점 기준으로 작성한 규범적 기대 정답입니다. `expected_table_ids`는 내부 검색 후보 목록이 아니라 이 골드에서 기대하는 표 집합입니다. 표·계열 코드와 정답 집합은 정확히 일치해야 합니다. 내부 검색 후보 순위와 모델의 설명 문구는 채점 대상이 아닙니다. 의미가 모호하면 `need_clarification`, 요청을 카탈로그에서 충족할 수 없으면 `no_match`로 둡니다. 기간이 빠진 선택 사례는 Agent의 기본 조회 계획을 기록하되 API 후속 상태를 `need_period`로 둡니다. 명시 기간이 있는 사례도 이 데이터셋에서는 수치 실행을 하지 않으므로 후속 API 상태는 `need_period`이며, 기간 선택 자체를 다시 요청하는지는 `post_discovery`에 따로 기록합니다.

## 범위와 한계

- 평가는 통계표 탐색까지입니다. KOSIS 수치 호출, 로컬 CSV 사용, 그래프 출력, 해석 문장 및 인과 주장 생성은 실행하거나 채점하지 않습니다.
- 정답 근거는 추적 가능한 공개 통계언어 사전의 메타데이터입니다. KOSIS 실시간 호출 결과나 실제 수치의 정확성을 뜻하지 않습니다.
- 자동 검증 통과는 골드의 사람 승인을 뜻하지 않으며, 모델 성능 점수로 해석하면 안 됩니다.
- `v1`, `eval/table-discovery/`, `eval/end-to-end/`, `eval/statbridge-golden/`와 버전 및 점수를 혼용하지 않습니다.
- 비공개 평가 저장소와 holdout 정답은 포함하지 않습니다.

## 검증

저장소 루트에서 실행합니다.

```bash
python3 eval/reporter-table-discovery-30/v2/scripts/validate.py
python3 -m pytest -q eval/reporter-table-discovery-30/v2/tests
```
