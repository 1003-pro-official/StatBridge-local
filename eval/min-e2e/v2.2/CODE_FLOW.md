# 코드 실행 경로와 평가 기준

분석 대상: C:/Users/<user>/Desktop/경진대회/StatBridge/StatBridge-local1. 전체 읽기 인덱스에 파일별 SHA-256·행 수·Python 함수 호출·JS/TS import/API 경로가 기록되어 있다. 자동 인덱싱과 주요 경로의 수동 추적을 병행했다. 비밀 .env 값과 비공개 holdout은 읽기 대상에서 제외했다.

1. Windows 시작 스크립트와 bootstrap/portable_runtime이 MCP, uvicorn bridge_api:app, Vite 프런트엔드를 준비한다. 프런트엔드 client.ts가 /api/query → /api/output → /api/output/edit를 호출하며 계정·세션·revision을 유지한다.
2. bridge_api.query는 query_conditions의 확인 질문을 파생 분류보다 먼저 처리한다. 따라서 QT21-11처럼 API가 먼저 확인 질문으로 끝난 경우 분류 함수의 결과와 실제 API 경로 관측을 구분해야 한다. 미관측을 오분류로 세지 않는다.
3. 일반 질의는 langgraph_workflow의 resolve_request → 확인 질문/미해결 또는 execute_statistics → prepare_output 순서다. 파생 질의는 분류 → 계획 → 표현식 검증 → 메타데이터·원자료 수집 → 계산 → 출력 순서이며 중간 blocked/error는 완료 응답이 아니다.
4. derived_indicator_planner.is_derived_request는 요청 연산과 공표 지표명을 구분한다. QT는 분류 전용이며 median/max-min 같은 질의의 엔진 연산 지원까지 이 지표의 정답으로 강제하지 않는다. expected_query_type과 predicted_query_type을 독립 보존하고 component_function / actual_api_route의 accuracy, precision, recall, F1, coverage를 각각 계산한다.
5. derived_indicator_runtime은 실제 inventory preflight와 expression_tree_validator를 통과한 계획을 가져온다. 실 API fetch는 prefer_local=False, allow_fallback=False 경로다. expression_tree_schema → validator의 과거 필요 구간 → DynamicExpressionExecutor가 연산 순서·시차·윈도·단위를 결정한다. D25/D27/D38의 B는 정의만 된 계열이며 원본 계획도 A만 사용한다. D32의 비율 이동평균과 D33의 이동평균 비율은 다르므로 정답을 합치지 않는다.
6. OutputAgent는 summary·display series를 만든 다음 table/chart의 출력 대상을 나눈다. 그러나 앞선 _apply_data_edits의 hidden label 필터가 이미 공통 series를 제거한다. 그래프 B 숨김이 표 B도 제거되는 현상을 직접 컴포넌트 실행으로 확인했다. 표 선택과 그래프 표시를 독립 검사한다.
7. 편집의 restore_initial은 세션의 최초 조회 초기 스냅샷을 복원한다. fixture 준비를 위해 수행한 제목·색상 편집은 초기 스냅샷을 바꾸지 않는다. E40/F34는 actual initial_query_snapshot과 fixture_ready_snapshot을 같은 실행에서 각각 수집해야 한다. 초기 상태를 fixture로 주입하지 않는다.
8. research_plotly_styles.cartesian_traces는 markers가 꺼져 있으면 marker size를 0으로 만든다. 점 색상만 지정하는 직접 명령에서 색상 저장과 크기 0을 확인했다. 자연어 명령 생성은 이번에 실행하지 않았다. 렌더된 크기·색상·위치·가림 여부를 함께 검사한다.
9. SVG/PDF는 report_export와 Matplotlib 경로, 화면 PNG는 workspaceDownload/Plotly 경로를 사용한다. 파일 존재·해시만으로 화면 일치를 승인하지 않는다. 로컬 합성 SVG probe에서는 바깥 구간 기본색을 보존했으므로 PC-1의 F26/F37 색 변경을 로컬 재현했다고 주장하지 않는다. 원 SVG의 요소·범위·색과 당시 화면이 필요하다.

DA는 현재 승인 메타데이터와 보존된 공식 스냅샷의 지표·분류·기간·단위를 검사한다. 현재 카탈로그에 SNA 기준이 있다는 사실을 과거 RAGAS context에 소급 삽입하지 않는다. 이 코드 경로 검토는 로그인·자연어 모델·실 API·브라우저 E2E의 성공 증거가 아니다.
