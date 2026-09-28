# 이전 StatBridge 코드 선별 이식 설계

## 목표

이전 `ClaBi/main`에서 동작하는 표 탐색 코드를 현재 StatBridge로 가져와, 현재 카탈로그와 347개 CSV로 질문에 대한 후보 표 ID와 검색 근거를 표시한다. 현재 `golden-set-v3`는 유지한다.

## 선택

- Backend/MCP: 이전 `statbridge_mcp`의 검색·메타·자료 조회 코드를 `src/backend/`에 배치한다. 작은 메타 CSV 3개만 가져오고, 현재 `data/tables/`를 참조한다. `merge_datasets`와 `render_chart`는 구현된 기능처럼 노출하지 않는다.
- Agent: 질의 해석·검색 파이프라인과 HCX 어댑터만 `src/agent/`에 가져온다. 실행 키가 없을 때도 Backend 검색을 직접 확인할 수 있게 한다.
- Frontend: 이전 React/Vite 화면의 스타일과 기본 구성을 재사용하되, 데모 수치 차트는 가져오지 않는다. 실제 후보 표만 보여준다.
- 연결: `POST /api/query`는 검색 결과의 `table_id`, 표명, 점수, 경로를 반환한다. 수치 조회와 골든셋 채점은 이 단계의 UI 범위에 넣지 않는다.

## 제외

이전 `eval/`, `golden-set*`, `experiment/`, `jev.py`, 777MB 중복 CSV, 가상환경, 빌드 산출물, 이전 `.env`, 완료되지 않은 병합·차트 도구는 가져오지 않는다.

## 확인

MCP 검색, Agent→Backend 검색, HTTP 요청, Frontend 빌드를 각각 확인한다. UI는 결과를 탐색 후보로 표시하며 확정 정답이나 수치를 주장하지 않는다.
