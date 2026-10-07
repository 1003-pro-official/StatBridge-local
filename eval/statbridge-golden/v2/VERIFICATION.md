# 제작 검증 기록

아래는 UI 정합성 수정 전의 관측입니다. 현재 사례의 검증·점수와 섞지 않습니다.
최신 범위는 [UI_REVISION.md](UI_REVISION.md), 최신 로컬 결과는 results/UI_REVISION_REPORT.md입니다.

## UI 정합성 수정 후 최종 확인

- 공개 dev 30·test 42건: 근거 포함 검증 오류 0·경고 0, 사람 승인 0.
- 원자료 독립 대조: 59개 계열·502개 시점, 불일치 0. 편집 6건의 정답 계산 불일치 0.
- 전체 pytest: 135 passed, 355 subtests passed.
- v4.1 검증기: VALIDATION OK. 기존 프런트엔드 빌드: 성공, 큰 번들 경고 유지.
- 새 공개 실행 72건: 관측 49·실행 오류 23. 채점은 자동 통과 23·실패 49.
- 자동 통과 중 해석 검수 대기 17건. 공식 승인본 성공으로 집계하지 않음.
- 노트북: Python exec로 코드 셀 12개, 그래프 2개, 새 저장 관측 72건 확인.
- Jupyter 커널, 브라우저 UI 조작, KOSIS/NCP live 호출은 미실행.
- 오프라인 편집 명령 재생은 자연어 편집 분류 검증이 아님.
- 기존 18개 첨부 사례는 내부 테스트에 보존했으며 공개 점수와 혼합하지 않음.

아래 초판 기록과 현재 결과를 혼동하지 않습니다.

2026-10-07, ai-assisted. 사람 승인 및 live 검증을 대신하는 기록이 아닙니다.

| 검사 | 실제 관측 결과 |
|---|---|
| 공개 72건 validate.py --verify-sources | 오류 0, 경고 0, 사람 승인 0 |
| 기존 tests + v4.1 tests + v2 tests 통합 pytest | 노트북 추가 후 97 passed, 355 subtests passed |
| 기존 v4.1 validate_v41.py | VALIDATION OK |
| 프런트엔드 pnpm build | 성공, 기존 대형 번들 경고 있음 |
| 대표 12건 오프라인 실행 | 실제 API/OutputAgent 경로 실행 및 채점 확인 |
| 공개 dev/test 오프라인 실행 | 30/42건 실제 실행, 관측과 오류를 results/에 저장 |
| KOSIS/NCP live 실행 | 미실행: 이번 제작은 오프라인 검증 범위 |
| 사람의 정답 승인·응답 해석 검수 | 미실행: 검수 양식 준비, 전부 대기 |
| 검토 노트북 | Python으로 코드 셀 12개 실행 확인, 참고도·실제 Plotly 2개 확인 |

노트북 검증은 ipykernel 없이 Python으로 셀을 실행한 것입니다.
현재 프로젝트 가상환경에 Jupyter 커널은 설치되어 있지 않아 Jupyter UI에서의 커널 실행은 미검증입니다.
원본 노트북은 출력 없이 관리하며 출력 미리보기는 results/review-preview.ipynb에만 보관합니다.

Windows 샌드박스에서 TestClient의 asyncio 로컬 소켓이 정지해 원인을 확인했고,
일반 권한으로 오프라인 재실행했습니다. 외부 HTTP 차단과 고정 공급자는 유지했습니다.
프런트엔드도 샌드박스의 node_modules realpath 권한 오류 뒤 일반 권한 재시도로 빌드했습니다.

원본 18개 KOSIS CSV에서 필요한 계열·기간만 fixture로 추출했습니다.
이는 347개 전체 원자료나 실시간 외부 조회가 모두 검증되었다는 뜻이 아닙니다.
모든 실행 예측·채점·해석 검수 결과는 Git에 넣지 않는 results/ 아래에 있습니다.
기존 v1 및 서비스 API에는 이번 작업의 변경을 적용하지 않았습니다.
# 2026-10-07 신뢰성 보완 검증

아래의 초기 기록과 구분한 최신 검증입니다. ai-assisted, 사람 승인 0건입니다.
전체 pytest: 129 passed, 355 subtests passed.
공개 72건 strict 검증: 오류 0, 경고 0.
독립 원본 대조: 876점 불일치 0, 변환·스타일·필터 8사례 계산 불일치 0.
v4.1 검증기 및 프런트엔드 빌드 성공. 큰 JS 번들 경고는 남아 있습니다.
노트북: Python exec로 코드 셀 12개 및 그래프 2개 확인. 실제 Jupyter 커널 UI 검증은 하지 않았습니다.
변경 규칙과 한계는 HARDENING.md, 실행 관측과 상세 보고서는 Git 제외 results/HARDENING_REPORT.md에 있습니다.
전체 72건의 새 실행과 live 검증은 이번 단계에서 수행하지 않았습니다.

