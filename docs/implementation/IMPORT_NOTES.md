# Backend·MCP 작업물 이관 기록

## 출처와 경계

기존 비Git 작업 폴더의 `src/backend/`, `StatBridge-official/`, `data/processed/`, `golden-set-v4.1-public/`을 현재 저장소 구조에 맞춰 반영했다. 현재 저장소에 이미 존재하던 v1·v2 평가셋과 이전 검색 API는 보존했다. 현재 UI가 사용하는 주 API는 `src/agent/bridge_api.py`다.

비공개 holdout 정답과 평가기, `.env`, 가상환경, `node_modules`, 빌드 산출물, Chroma DB, 임베딩 캐시, 임시 평가 결과는 이 저장소에 넣지 않는다. 비공개 평가기는 PM이 관리하는 별도 접근 제한 저장소에서만 사용한다.

## 데이터 공급

`data/processed/`에는 메타데이터 CSV 6개를 둔다. 347개 원자료 CSV는 별도 원본에서 `data/tables/`로 공급하거나 `STATBRIDGE_TABLES_DIR`로 지정한다. 이 폴더가 없으면 검색과 카탈로그는 가능하지만 로컬 관측값 조회는 확인할 수 없다. 실제 KOSIS와 NCP 호출은 각 API 키가 있는 환경에서 별도로 검증한다.

## 재현

루트 `README.md`의 설치·실행·평가 명령을 따른다. 현재 위치 `eval/table-discovery/v4.1/`의 holdout 파일에는 질문만 있으며, 개발 중 평가는 dev/test로 수행한다. `tools/evaluate_golden_v41.py`의 결과는 `eval/results/`처럼 Git에서 제외한 경로에 기록한다.
