# 기자 자연어 질의: 통계표 탐색 골든셋 30개

한국은행 보고서를 취재하는 기자가 자연어로 그래프와 해석을 요청하는 상황을 위한 공개 개발용 초안이다. 실제 평가 범위는 **질문 해석부터 통계표·항목·분류값·조회 계획의 확정까지**다.

- 작성일: 2026-10-08
- 스키마: `reporter30-draft-2`
- 근거 사전: `src/agent/stat_dictionary/stat_language_dictionary.json` v5.1
- 문항: 30개, 정답 계열: 57개, 정답 통계표: 26개
- 구성: 단일 계열 8개 / 같은 표의 복수 계열 10개 / 여러 표의 복수 계열 12개
- 검수: `ai-assisted`, 메타데이터 코드 대조 완료, `human_approved=false`
- 모든 문항은 정답이 공개된 `dev` 자료이며 블라인드 holdout이 아니다.

## 파일

| 파일 | 내용 |
|---|---|
| [statbridge-reporter30.jsonl](statbridge-reporter30.jsonl) | 30개 질문과 기계 판독용 정답 |
| [statbridge-reporter30.md](statbridge-reporter30.md) | 질문, 단계별 정답, 정확한 계열 코드, research 근거 |
| [dataset_manifest.json](dataset_manifest.json) | 버전, 문항·계열 수, 정답 사전과 데이터셋의 SHA256 |
| [scripts/validate.py](scripts/validate.py) | 정답 코드와 단계별 정합성을 다시 확인하는 검증기 |
| [tests/test_validate.py](tests/test_validate.py) | 잘못된 분류 코드·측정 기준·누락 계열을 거부하는 회귀 테스트 |

## 정답과 판정 범위

각 문항의 `workflow_gold`에 다음을 기록했다.

1. `query_interpretation`: 지표, 대상, 측정값, 측정 기준, 세부 조건, 기간, 주기, 비교 여부
2. `table_discovery`: 정답 통계표 이름과 ID 집합
3. `item_selection`: 표별 항목 코드
4. `classification_and_plan`: 계열별 분류값 이름·코드, 기간, 주기
5. `resolution`: 정답 상태, 표 수, 계열 수, 통계 의미 역질문 필요 여부

자연어 슬롯은 같은 뜻의 표현을 허용하되 대상·측정 기준을 바꾸면 안 된다. 표 ID와 계열 코드 집합은 순서와 무관하게 정확히 일치해야 한다. 일부 계열 누락이나 추가 계열은 통과로 처리하지 않는다. UI의 기간·그래프 설정 확인은 통계 의미를 묻는 역질문과 구분한다.

기간은 2023~2024년 전체다. API 기간은 월별 `202301`~`202412`, 분기별 `202301`~`202404`다. `null`은 추가로 명시한 조건이 없다는 뜻이며 더 좁은 대상으로 추측하지 않는다.

## 검증 상태와 한계

저장소 루트에서 실행한다. Windows에서는 `.venv/bin/python` 대신 `.venv\Scripts\python.exe`를 사용한다.

```bash
.venv/bin/python eval/reporter-table-discovery-30/v1/scripts/validate.py
.venv/bin/python -m pytest -q eval/reporter-table-discovery-30/v1/tests
```

검증기 출력은 정합성 확인 결과이며 모델 정답률이 아니다. 로컬 작성 기록 `statbridge-reporter30-validation.json`은 버전 관리에서 제외한다.
SHA256은 UTF-8 바이트의 줄바꿈을 LF로 통일해 계산한다. Windows 체크아웃의 CRLF와 Git의 LF 차이로 검증 결과가 달라지지 않도록 한다.

30개 문항 ID·질문의 유일성, 57개 의미 슬롯과 정답 계열의 대응, 사전의 표·항목·분류 코드, 기간·주기·측정 기준, 연구 자료 제목·결과물 ID의 정합성을 확인했다. 연구 문서의 자동 추정 필드를 코드 정답이나 실제 관측값으로 사용하지 않았다.

시스템 예측과 실제 KOSIS/CSV 수치 조회는 실행하지 않았다. 개별 계열 수록기간·결측·단위는 실제 조회 시 추가 확인이 필요하다. 그래프와 해석은 요구사항만 있으며, 원자료 스냅샷과 수치 정답이 확정된 완성된 E2E 골든셋이 아니다. 자동 채점기는 아직 구현하지 않았다.

기존 `table-discovery/v4.1`, `end-to-end`, `statbridge-golden`의 버전·점수와 별도로 관리한다. 이 JSONL은 v4.1 검증기·채점기의 입력 스키마와 호환된다고 주장하지 않는다. 사람 검수 전에 공식 성능 지표로 사용하지 않는다.

비공개 평가 저장소, 비공개 holdout 정답, API 키, 원자료 CSV를 포함하지 않는다. 생성용 임시 스크립트는 이 폴더에 복사하지 않았다.
