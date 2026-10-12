# 그래프 워크스페이스 실행 증거

2026-10-12 · ai-assisted. API 검증과 실제 브라우저 검증을 구분한다. 생성 증거는 개인정보·대용량 파일의 자동 게시를 피하기 위해 기존 ignored `evaluation_runs/` 아래에 보관한다. 문서는 코드와 함께 검토할 수 있다.

## 자동 검증

```powershell
$env:PYTHONPATH='src/backend;src/agent'
$env:HF_HUB_OFFLINE='1'
.venv/Scripts/python.exe -m pytest -q tests eval/table-discovery/v4.1/tests
.venv/Scripts/python.exe eval/table-discovery/v4.1/scripts/validate_v41.py
pnpm --dir src/agent/frontend build
```

최종 결과: **741 passed, 355 subtests passed, 402.26초**. Node의 이력 지시·출력 지시·좌표 편집 검증 8개도 통과했다. v4.1 검증은 `VALIDATION OK`, dev/test/holdout 50/70/30이며 비공개 정답을 읽지 않았다. 프런트엔드 빌드는 성공했고 기존 대형 Plotly 번들 경고는 남아 있다. 로그는 `evaluation_runs/chart_workspace_live/full-regression.log`, `frontend-build.log`다.

실제 서버를 별도 포트 8005, 프런트엔드 5174로 실행하여 기존 실행 서비스를 유지했다. `scripts/validate_chart_workspace_live.py`는 실제 `/query`→`/output`→편집→내보내기→저장을 수행한다. `--help`로 인자를 확인할 수 있다. 실제 외부 호출을 포함하므로 키와 네트워크가 필요하다.

## 실제 API

최종 `evaluation_runs/chart_workspace_live/evidence.json`: PASS, 편집 버전 25, 관측값 24개. 자료는 한국은행·KOSIS DT_181Y011, 단위 십만원, 202001–202504다. 첫 값 1242.5, 마지막 값 2128.6이다. 원자료 표 해시는 `e637bd467fe5b234c775c05486f9fc4c9d6c85a9b32be0fd1ce3587abe714f51`이다.

6개 디자인 적용 → 제목/색/강조/기준선/범례/디자인/설명/두께/격자/부제 10회 편집 → Undo/Redo → JSON 복원·재편집 → 자연어 제목/분기 강조/최근 강조 색/불투명도/선 색 → PNG/SVG/PDF → 서버 저장을 검사했다. 각 표현 변경 단계에서 같은 표 해시를 확인한다.

초기 실행에서 기본 디자인과 같은 선 두께 설정을 무변경으로 거절하던 문제를 발견해 상태 변경 판단을 수정했다. 실제 HCX 실행 중 429 제한이 발생했고 제한적 재시도 후 다섯 자연어 편집이 통과한 회차가 있었다. 이후 반복 회차에서 명확한 분기 강조에 모델이 빈 명령을 반환했다. 그 실패를 숨기지 않고 `failure.json`에 남겼으며, 제한된 현재 상태 기반 텍스트 해석을 추가한 뒤 최종 실행을 통과했다. 최신 간단한 다섯 지시의 `edit_agent.model`은 `validated-text`다. 최신 성공을 HCX의 모든 자연어 이해 성공률로 해석하지 않는다.

실제 출력 파일은 `actual-chart.png`, `actual-chart.svg`, `actual-chart.pdf`. PDF는 Poppler로 `pdf-preview.png`를 렌더링하여 한글 제목·축·기간·기준선·음영·출처·범례와 격자 설정을 육안 점검했다.

## 브라우저

데스크톱 1600×850에서 다음 순서로 조작했다. `evaluation_runs/chart_workspace_browser/`에 증거를 보관한다.

1. 실제 DT_181Y011 질문→선 그래프 생성: `01-before.png`.
2. report/stability/outlook/slides/academic/explore 적용: `design-*.png`, 버전 1–6.
3. 제목→기간 강조→기준선→범례→디자인→설명→두께→세로 격자 제거→가로 격자 제거→부제: 버전 6→16, `manual-10-edits.png`. 이 10회에는 도구로 시도했으나 반영되지 않은 native color 입력을 성공으로 포함하지 않는다.
4. 제목·선·세로축·설명을 실제 그래프에서 클릭해 각각 제목 선택/선택한 데이터/세로축 선택/설명 선택을 확인했다.
5. Undo로 부제가 이전 값으로 복원되고 Redo로 다시 반영되는 것을 확인했다. 하단 자연어로 제목을 바꾸고 기존 강조/기준선/설명이 유지되었다: `natural-and-manual.png`.
6. 설정 저장→임시 제목 변경→최근 저장 설정 열기→추가 부제 편집: `saved-reedit.png`.
7. DT_513Y001 경제심리지수 원계열 월별 72개를 실제 조회·추가: `actual-data-added.png`. 해당 계열 제외·재표시, 전체 항목 변경: `actual-data-replaced.png`. Undo로 두 자료 복원: `data-undo.png`.
8. 저장→직접 실행한 검증 서버 재시작→브라우저 새로고침→추가 부제 편집: `restart-reedit.png`, `restart-response.json`, 버전 31. 편집 전후 원자료 표 해시가 동일하다.
9. 다운로드 메뉴에서 PNG·SVG·PDF 파일 다운로드를 실제 확인했다: `downloads.json`. 다운로드 완료 확인에 브라우저 도구 지연이 있었으며 이를 앱 편집 API 지연으로 집계하지 않는다.
10. 모바일 390×844에서 가로 overflow 없음과 하단 입력창 고정 위치(하단 836px)를 확인했다: `mobile-390.png`. 모든 모바일 기능을 전수 검사한 것은 아니다.

`final-fullpage.png`는 실제 전체 페이지 캡처다. `final-bounds.json`에 기록한 실제 DOM 구역만 잘라 `final-workspace.png`로 제공하며 그래프·문구·설정을 합성하지 않는다. `design-comparison.png`는 첨부 참고 이미지와 그 실제 캡처를 나란히 배치한 비교 자료다.

## 남은 범위

실제 Jev 호출은 키 부재로 BLOCKED. 모든 등록 통계표의 실시간 조회·모든 차트 조합·모든 복합 자연어·사람 대상 사용성 검사는 NOT TESTED. HTTP 오류/모호한 지시에서 기존 그래프 보존, 저장 변조 거절, 이전 버전 거절은 자동 회귀 테스트로 검증했다.
