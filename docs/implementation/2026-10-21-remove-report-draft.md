# 보고서 초안 기능 제거 (2026-10-21)

ai-assisted. 사용자의 삭제 요청에 따라 local1과 StatBridge1에서 별도 보고서 초안 기능을 제거했다. 보고서 작성 대화·MD 모으기/미리보기/내려받기, 그래프·표 내보내기는 유지한다.

## 삭제한 전용 파일

- src/agent/frontend/src/ReportDraft.tsx
- src/agent/frontend/src/reportDraftDocument.ts
- src/agent/frontend/test-report-draft.mjs (공용 크기 검사 3건은 test-chart-output-size.mjs로 이동)
- src/agent/report_caption.py
- src/agent/report_interpretation.py
- src/agent/report_draft_export.py
- tests/test_report_caption.py (공용 숫자 표시 검사는 test_report_summary.py로 이동)
- tests/test_report_interpretation.py
- tests/test_report_draft_pdf.py

초안 요청 모델·생성/문헌 검색·세션 초안 캐시 작성·HTML 인쇄·PDF 생성과 /api/report/interpret 및 /api/report/draft/export 경로도 제거했다. App 전용 크기 측정 ref·콜백, 관련 CSS, 미사용 resizeReportChart와 샘플 환경설정 STATBRIDGE_REPORT_PASSAGES를 정리했다. 과거 기록 문서·검증 결과와 기존 저장 분석은 삭제하지 않았다. 폐기한 모듈의 pyc 12개도 두 폴더에서 정리했다.

report_caption에 있던 display_number는 보고서 대화·변화 설명·관측점 라벨이 사용하므로 report_summary로 원형을 옮겼다. 소수점·작은 비영 수치 보존을 그대로 검사한다. 일반 PNG 내보내기와 출력 크기 UI가 쓰는 reportChartSize/validateChartSize는 공용 기능이므로 보존한다.

## 검증

- 두 폴더 프런트엔드 TypeScript 미사용 선언 검사 포함 빌드 PASS, Node 217 PASS.
- 두 폴더 관련 Python 회귀 각 112 PASS. 보고서 질문/후속 문맥/MD 저장·내보내기/숫자 표시/관측점/형식 검사를 포함한다.
- 전체 Python 수집 2,218건 성공. 이는 전체 테스트 실행 성공률로 표기하지 않는다.
- 두 실제 백엔드를 신원 확인 후 재시작했다. health 200, 공개 OpenAPI에서 초안 전용 두 경로가 없고 질문·대화·MD 경로가 남아 있음을 확인했다.
- 두 UI에서 실제 금리 조회를 실행하여 ‘보고서 초안’ 표기가 0개이며 ‘보고서 작성하기’, 질문 입력, MD 미리보기/내려받기가 남는 것을 확인했다. local1에서 실제 보고서 질문 응답도 확인했다.
- 데이터·.env·계정 DB·기존 분석과 기록 문서는 초기화하거나 복사하지 않았다. 전용 모듈명에 대한 실행 소스/테스트/도구의 남은 참조는 0건이다.
