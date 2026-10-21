# 셀 직접 편집 검증 결과

2026-10-19, local1 및 StatBridge1/StatBridge-official에 동일 소스를 적용했다. 원본 업로드 자료와 사용자 계정·저장 분석·환경 설정은 보존했다.

## 자동 평가

| 실행 대상 | 실행/통과 | 실패 | 미실행 |
|---|---:|---:|---:|
| local1 공개 전체 Python 회귀 (94개 파일) | 1989 / 1989 | 0 | 0 |
| 위 실행의 하위 검사 | 355 / 355 | 0 | 0 |
| local1 첨부 표 관련 평가 (전체 회귀와 중복) | 111 / 111 | 0 | 0 |
| StatBridge1 첨부 표 관련 평가 | 111 / 111 | 0 | 0 |
| local1 프론트엔드 Node 테스트 | 169 / 169 | 0 | 0 |
| StatBridge1 프론트엔드 Node 테스트 | 169 / 169 | 0 | 0 |

두 폴더 TypeScript/Vite 빌드와 v4.1 계약 검사도 통과했다. Vite의 큰 번들 경고는 남아 있으나 빌드 오류는 없다. 전체 Python 회귀 도중 Python 소스/테스트 해시 변경 없음. StatBridge1에서 전체 1989건을 별도 재실행하지는 않았고 동일 소스 확인 및 관련 111건으로 검증했다. 중복 실행을 새로운 독립 사례 수로 합산하지 않는다.

표 편집 관련 평가는 요청 전 HTTP를 차단하고 모델 키를 자식 프로세스에서 비활성화했다. 표 직접 편집/관련 평가의 GPT 호출은 0회. 전체 Python 회귀도 모델 키 비활성 상태다. 이는 실시간 GPT·KOSIS 품질 평가가 아니다.

## 실제 브라우저 및 파일

- 격리된 참조 서버에서 PDF 5쪽의 3열 병합 머리글을 분할하고 빈 피복 셀이 다시 나타나는 것을 확인했다.
- PDF 13쪽의 연간 행 제목 두 셀을 세로 병합하여 rowspan=2를 확인했다.
- PDF 18쪽의 B4:C5를 Shift+클릭과 실제 마우스 드래그로 선택하고 노란색 채우기·2×2 병합·분할·우클릭 테두리를 적용했다. rowspan=2, colspan=2와 분할 후 네 수치 복원을 확인했다.
- 제목 더블클릭/F2 편집, Enter/다른 셀 이동 반영, 되돌리기/다시 실행, 열 경계 방향키 조절 및 마우스 드래그를 실행했다.
- 격리된 계정에서 저장 후 페이지 재로드/보관함 복원으로 변경 제목과 범위 채우기를 확인했다.
- 같은 18쪽 편집 결과를 브라우저로 XLSX/PDF/PNG/CSV 다운로드했다. XLSX B6:C7 병합, 노란색, 네 값 모두 보존, 계산근거 60행(+머리글)을 openpyxl로 검증했다. PDF 1쪽/추출 텍스트 1009자, PNG 1164×800, CSV 1583바이트. PNG를 열어 표와 병합·색상·주석 표시를 시각 점검했다. CSV는 서식이 아닌 텍스트 출력이다.
- 재시작한 실제 local1(8000/5173)과 StatBridge1(8001/5174)에서 기존 저장 분석을 열고 표→셀 직접 편집 시작→범위 색칠을 확인했다. local1에서는 두 수치를 가로 병합해 XLSX를 실제 다운로드하고 B4:C4, 하늘색, 원래 두 수치와 계산근거 20행을 확인했다.
- 기존 정상 계정의 분석 저장 파일은 덮어쓰지 않았다. 저장/복원 편집 검증은 격리 계정에서 수행했다. 정상 계정에서의 미저장 편집은 서버 세션에만 남는다.

## 보존 확인

재시작 후 test1의 기존 저장 분석 local1 5개, StatBridge1 2개를 모두 HTTP 200으로 복원했다. users/graphs 레코드와 저장 JSON.gz 및 .env의 작업 전후 SHA256이 일치한다. local1 users 5/graphs 9, StatBridge1 users 4/graphs 5. 기존 브라우저 임시 대화는 별도이며 최신 5개 외 기록을 삭제하지 않는다.

## 한계 및 재현

수치 직접 덮어쓰기, Excel 수식 입력, 임의 행·열 추가, 25쪽 전체 픽셀 재현은 이번 범위가 아니다. 색상과 병합을 자유롭게 바꾸는 표시 편집이며 원자료·계산식 검증 경로를 유지한다. 실제 KOSIS·GPT 계획 평가는 이번 변경에서 실행하지 않았다.

```powershell
.venv/Scripts/python.exe tools/run_table_edit_eval.py --out .venv/cache/table-sheet-20261019/evaluation
.venv/Scripts/python.exe tools/run_table_edit_regression.py --out .venv/cache/table-sheet-20261019/regression-final
cd src/agent/frontend
node --test test-*.mjs
npm run build
```

로그·개별 판정·보존 해시·UI 스크린샷은 각 프로젝트의 .venv/cache/table-sheet-20261019에 보관한다. 원본 ZIP/PDF·계정 DB·생성 파일·개인 경로 포함 로그는 공개 소스에 넣지 않는다.
