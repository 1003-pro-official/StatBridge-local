# StatBridge 골든셋 v3: 표 탐색·판단 초안

이 폴더의 30건은 **개발용 초안**입니다. 활성 골든셋의 ID는 `GS-0001`~`GS-0030`이며 이전 버전과 병합하지 않습니다. 모든 사례의 `split`은 `dev`, `review_status`는 `review_required`이고 사람 승인 건수는 0건입니다. 수치·조회 파라미터·차트 결과는 정답 범위에 포함하지 않습니다. 이전 v1·v2는 같은 `table-discovery/` 아래에 별도로 보존합니다.

| 유형 | 건수 | 기대 결과 |
|---|---:|---|
| 단일 표 `single` | 10 | 표 ID 1개 선택 |
| 복수 표 `multi` | 4 | 필요한 표 ID 집합 선택 |
| 역질문 `clarify` | 5 | 표 확정 전 구분 조건 확인 |
| 범위 내 무결과 `no_match` | 3 | 프로젝트 목록 안에서 대응 표 없음 제안 |
| 목록에만 있는 표 `catalog_only` | 2 | 표 ID를 찾고 로컬 수치 조회 중단 |
| 후속 대화 `followup` | 6 | 선행 조건을 유지하고 새 조건을 반영 |

## 파일과 기준

- `cases.jsonl`: 기계 평가용 정본 초안. `query`는 마지막 사용자 발화이며, 후속 대화는 `prior_turns`에 기록합니다.
- `review.csv`: 사람이 읽고 판정할 UTF-8(BOM) 검토표. ID 목록은 셀 안에서 세미콜론(`;`)으로 구분합니다.
- `scripts/manage_v3.py`: 구조·출처 검증, 검토 CSV 내보내기, 검토 의견 가져오기. Python 표준 라이브러리만 사용합니다.

카탈로그는 `data/kosis/hankook_tables.json` 349표, 수집일 2026-09-14 스냅샷입니다. SHA-256은 `cbe3e941ba3ecd733711fa86c75528fe6531250b25062c710c0387709e0a5f3e`입니다. 선택 사례의 근거는 `data/tables/*.csv`의 실제 항목·분류 코드, `PRD_SE`, `PRD_DE`에서 확인했습니다. 로컬 CSV는 347개입니다. `DT_284Y001`과 `DT_284Y002`는 목록에 있으나 해당 CSV가 없어 `catalog_only`로 분리했습니다.

`no_match` 3건은 349표의 제목·경로와 347개 CSV의 문자 검색에 근거한 **미승인 제안**입니다. 전체 KOSIS 검색이나 통계적 의미의 대체 표 검색을 마쳤다는 뜻이 아닙니다. 사람 검토에서 대응 표를 찾으면 라벨을 수정해야 합니다.

## 라벨 읽기

- `expected_status=select`: `table_ids`의 모든 표가 필요합니다. 단일 표는 1개, 복수 표는 2개 이상입니다.
- `expected_status=clarify`: `table_ids`는 비어 있습니다. `candidate_table_ids`는 가능한 표 후보이고 `clarification_dimension`이 필요한 질문 조건입니다.
- `expected_status=no_match`: 선택·후보 ID는 비어 있으며 검색 범위와 근거를 검토해야 합니다.
- `expected_status=catalog_only`: `table_ids`는 탐색 정답이지만 로컬 CSV가 없어 수치 조회는 진행할 수 없습니다.
- `slots.metrics`는 사용자의 표현을 기록하고, 표 검색용 정규화 표현은 `normalized_concepts`에 둡니다. 후속 질의에서는 선행 발화의 조건을 이어받은 값도 포함합니다. 지정되지 않은 대상·기간·주기는 `null`입니다.

## 사람 검토

1. `review.csv`에서 원문·선행 대화·슬롯·후보·근거를 확인합니다. **앞의 제안 열은 수정하지 말고** `decision`, `approved_table_ids`, `reviewer`, `reviewed_at`, `review_notes`만 입력합니다.
2. `decision`은 `승인`, `수정`, `보류`, `제외` 중 하나입니다. `승인`에는 검토자 이름을 입력합니다. `select`·`catalog_only`의 승인 ID는 제안된 전체 `table_ids`를 세미콜론으로 기록합니다. `clarify`·`no_match` 승인 ID는 비워 둡니다. `수정`·`보류`·`제외`에는 이유를 메모에 적습니다.
3. CSV 저장 후 프로젝트 루트에서 실행합니다:

   ```bash
   python3 eval/table-discovery/v3/scripts/manage_v3.py import-review eval/table-discovery/v3/review.csv
   python3 eval/table-discovery/v3/scripts/manage_v3.py validate
   ```

가져오기는 30행을 모두 검사한 뒤 **`review` 필드만** 정본에 저장합니다. 제안 라벨과 `review_status`는 바꾸지 않습니다. 수정 의견을 반영하고 사람 승인 상태를 확정하는 절차는 다음 검토 단계에서 진행합니다. 검토자가 편집한 CSV를 덮어쓰지 않도록 `export-review`는 기존 파일이 있으면 중단합니다.

검증 테스트: `python3 -m unittest discover -s eval/table-discovery/v3/tests -v`. 전체 사례 검증에는 별도로 공급한 `data/tables/` 원자료 CSV가 필요합니다. 최종 블라인드 테스트 문항은 개발용 30건과 따로 팀이 작성해 보관합니다.
