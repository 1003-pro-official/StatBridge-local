# 셀 선택 자동 스크롤 (ai-assisted)

셀 선택은 pointerenter만 처리해 화면 밖 셀로 이어지지 않았다. 선택 드래그 중 requestAnimationFrame으로 표 스크롤 영역의 가장자리를 검사해 좌우·상하 이동하고, 포인터 아래 새로 드러난 셀을 hit-test하여 선택 끝점을 갱신한다. 합쳐진 셀은 기존 selectionRect가 확장한다. 원자료·서식·서버 세션은 변경하지 않는다.

- 가장자리 40px 안에서 거리에 따라 속도를 높이고 프레임별 최대 속도를 제한한다.
- 고정 행 번호·열 문자의 영역과 스크롤바를 제외한 실제 셀 위치로 hit-test한다.
- pointerup/cancel, 창 blur, 기본 버튼 해제, 편집·배치 변경, 컴포넌트 해제 시 animation과 이벤트를 정리한다.
- 별도 API/GPT 호출을 추가하지 않는다. 자동 스크롤·마우스 이동은 Langfuse 전송 대상에서 제외하는 것이 적합하다.

검증: 양쪽 프런트엔드 각각 186 PASS / 0 FAIL / 0 SKIPPED, TypeScript/Vite 빌드 PASS. 신규 7건은 속도 경계, 정지 포인터의 연속 스크롤·선택 확장, 왼쪽/위쪽, pointerup/cancel/blur/버튼 해제, 이벤트 정리를 검사한다. 백엔드 변경이 없으므로 Python 전체 회귀는 재실행하지 않았다.

실제 UI는 tools/serve_table_edit_preview.py의 고정 첨부 자료·격리 계정 DB, 별도 cookie/8005·5175 포트에서 검사했다. 기존 앱 로그인이 만료되어 사용자 계정을 변경하지 않았다. 실제 KOSIS 또는 모델 품질 평가로 보고하지 않는다.

기대인플레이션의 가로로 긴 표를 807px 뷰포트에 표시했다. 처음 scrollLeft=0에서 오른쪽 드래그 후 44px 이동하고 A1:G1 선택을 확인했다. 오른쪽에 누른 상태 유지 후 128px, 왼쪽 역드래그 후 84px로 줄며 A1:G1 선택을 유지했다. 실제 UI의 수직 스크롤은 별도 재현하지 않았으며 수직 계산·정리 동작은 신규 자동 검사 범위다.

스크린샷: .venv/cache/sheet-autoscroll-20261020/selection-autoscroll.png. 기존 계정·저장 분석·.env는 변경하지 않았다. Langfuse 연결은 별도 설계 문서의 제안 단계이며 이번 패치에 외부 전송 기능을 추가하지 않았다.
