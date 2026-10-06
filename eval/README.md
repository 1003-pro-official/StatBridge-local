# 평가 자료

버전 번호는 아래 두 계열 **안에서만** 이어집니다. 서로 다른 계열의 v1·v2를 합치거나 점수를 직접 비교하지 않습니다.

| 계열 | 경로 | 범위와 현재 상태 |
|---|---|---|
| 표 탐색 | [`table-discovery/v1`](table-discovery/v1/README.md) | ClaBi에서 가져온 150건 초안, 사람 승인 0건 |
| 표 탐색 | [`table-discovery/v2`](table-discovery/v2/README.md) | ClaBi에서 가져온 150건 구조 개선 초안, 사람 승인 0건 |
| 표 탐색 | [`table-discovery/v3`](table-discovery/v3/README.md) | ClaBi에서 가져온 dev 30건, 사람 승인 0건 |
| 표 탐색 | [`table-discovery/v4.1`](table-discovery/v4.1/README.md) | 공개 dev 50·test 70건과 정답 없는 holdout 질문 30건, 사람 승인 전 평가 준비본 |
| 전체 흐름 | [`end-to-end/v1`](end-to-end/v1/README.md) | 간행물 기반 150건·그래프 fixture 30건; 현재 측정값은 검색과 정답 계열을 지정한 로컬 그래프 데이터에 한정, 보류셋 개발 노출 |
| 전체 흐름 | [`end-to-end/v2`](end-to-end/v2/README.md) | v1 회귀 150건과 미작성 신규 사례 큐 50건; 출시 평가 준비 전 |
| 표 탐색+해석 | [`statbridge-golden/v1`](statbridge-golden/v1/README.md) | 자체 설계 계열(9계층·오답 함정·해석). 초기 시드 진행 중, 사람 승인 전 |

`table-discovery/v1`·`v2`·`v3`의 원본은 ClaBi 작업 폴더의 `golden-set-v1`·`golden-set-v2`·`golden-set-v3/golden-set-v3`입니다. 사례·검토 파일은 그대로 복사했고, 이 저장소에서 관리 스크립트의 경로만 조정했습니다. 초안에 전체 파이프라인 필드가 있더라도 승인된 전체 흐름 정답이나 수치 평가로 해석하지 않습니다.

`end-to-end/v1`·`v2`는 기존 StatBridge-local의 `eval/golden-set-v1`·`golden-set-v2`를 이동한 것입니다. `table-discovery/v4.1`도 기존 `eval/golden-set-v4.1`을 이동했습니다. `eval/retrieval/`은 별도 검색 실험 자료입니다.

개발 중 v4.1 평가는 공개 dev/test만 사용합니다. 비공개 holdout 정답과 평가기는 `StatBridge-evaluation-private`에만 두고 공개 저장소로 복사하지 않습니다. 원자료 CSV가 필요한 구버전 관리 명령은 `data/tables/`을 별도로 공급한 환경에서 실행합니다.
