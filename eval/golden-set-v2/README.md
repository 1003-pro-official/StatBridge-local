# 골든셋 v2 (초안)

`cases/v1_regression.json`은 기존 v1 사례 150개를 v2 형식으로 옮긴 회귀 평가 데이터입니다. 원본 `eval/golden-set/`은 수정하지 않았습니다. v1의 보류 평가 사례는 개발 중 검색 규칙 조정에 사용되었으므로, 블라인드 평가가 아니라 회귀 검사에만 사용합니다.

`authoring_queue.json`에는 합의한 신규 사례 50건의 작성 작업이 들어 있습니다.

- 후속 질문 20건
- 카탈로그 전용 10건
- 명확한 질문의 불필요한 역질문 여부 10건
- 그래프 전체 흐름 10건

이 큐는 아직 골든셋 사례가 아닙니다. 질문, 정답, 보고서 위치를 임의로 만들지 않았습니다. 실제 자료의 근거, 지원되는 ID, 필요한 fixture, 독립 검토를 채운 뒤 평가에 포함해야 합니다.

## 사례 정답 형식

v2는 `expected.resolution`에 의도, 역질문 유형, 정답 표 ID 집합, 검색 계열별 허용 ID를 기록합니다.

```json
{
  "intent": "resolved | ambiguous | unsupported",
  "clarification_kind": "none | semantic | table_selection | series_parameters",
  "table_ids": ["API가 제안해야 하는 정확한 표 ID 집합"],
  "retrieval_groups": [["필수 계열 하나에 허용되는 표 ID"]]
}
```

서비스 응답은 기존 `status`를 유지하면서 `resolution`을 추가로 반환합니다. 실제 제안된 표 ID는 서비스가 반환한 `resolution.proposed_table_ids`를 사용합니다. 평가기가 후보 순위나 정답 라벨을 보고 제안 표 ID를 사후 추정하면 안 됩니다.

## 실행

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python tools/build_golden_set_v2.py
PYTHONPATH=src/backend:src/agent .venv/bin/python tools/evaluate_golden_set.py --corpus eval/golden-set-v2
```

현재 검색 평가기는 옮겨온 회귀 사례를 평가합니다. 현재 API의 예측 결과를 저장한 뒤 v2 지표를 계산하려면 다음 명령을 사용합니다.

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python tools/predict_golden_set_v2.py --output /tmp/golden-v2-predictions.json
.venv/bin/python tools/evaluate_golden_set_v2.py eval/golden-set-v2/cases/v1_regression.json /tmp/golden-v2-predictions.json
```

예측 파일은 사례 ID를 키로 사용합니다. 각 값에는 API의 `resolution`, 같은 요청에서 받은 후보 순위 `ranked_table_ids`, 기존 응답 상태 `legacy_status`가 포함됩니다.

## 출시 전 완료할 항목

- 신규 공개 사례 50건의 근거와 정답을 채우고, 독립 검토를 거쳐 공개 사례를 총 200건으로 완성합니다.
- 새로운 비공개 사례 60건을 별도로 작성합니다. 질문과 정답은 이 저장소, 개발 프롬프트, 검색 인덱스에 포함하지 않습니다. 코드와 버전을 고정한 뒤 예측을 만들고, 공개 전에는 집계 점수만 공유합니다.
- 카탈로그 스냅샷과 수치 fixture의 해시를 기록합니다. 실시간 KOSIS 점검은 고정 fixture 평가와 분리합니다.
- R@5, Top-1, 단일 표 정확도, 다중 표 정확도, 역질문 민감도와 억제율, 후속 질문, 범위 밖 질문, 카탈로그 전용, 그래프 데이터 정확도를 각각 측정합니다. 그래프 화면은 별도로 사람이 확인합니다.

현재 매니페스트 상태는 `not_release_ready`입니다. v1 보류셋이 개발 중 노출되었으므로, 이를 근거로 블라인드 성능을 주장할 수 없습니다.
