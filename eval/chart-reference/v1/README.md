# 한국은행 참고 그래프 형식 재현 진단 v1

공식 공개 보고서에서 선택한 그래프 3개를 첨부해 `이렇게 그려줘`를 요청하는 진단 하네스입니다. 표 탐색 200문항 점수와 독립적이며, 3개 예시의 통과를 일반적인 VLM 정확도·동일 픽셀 재현으로 주장하지 않습니다.

- 경제전망보고서(2026년 5월), PDF 28쪽: 그림 1.18 선 그래프 / 그림 1.19 누적 막대 그래프
- 금융안정보고서(2026년 6월), PDF 22쪽: 그림 I-1-6 패널 그래프
- `cases.json`에 공식 게시글·PDF URL, 페이지, crop 좌표, 현재 local1 카탈로그의 실제 조회 조건과 기대하는 기본 표현을 기록했습니다. 공개 보고서·PNG·평가 결과·모델 응답·임시 계정은 커밋하지 않습니다.

## 실행

루트의 Python 가상환경, 현재 KOSIS 데이터/연결, 설정된 이미지 입력 OpenAI 모델을 사용합니다. `pdftoppm`이 PATH에 없으면 `--pdftoppm <실행 파일>`로 지정합니다.

```powershell
.venv/Scripts/python.exe scripts/prepare_bok_vlm_samples.py --output-dir .venv/cache/bok-vlm/samples
.venv/Scripts/python.exe scripts/evaluate_chart_references.py --samples .venv/cache/bok-vlm/samples/samples.json --output-dir .venv/cache/bok-vlm/prepare
.venv/Scripts/python.exe scripts/evaluate_chart_references.py --samples .venv/cache/bok-vlm/samples/samples.json --output-dir .venv/cache/bok-vlm/live --live
```

`--live`는 실제 유료 모델 요청을 실행합니다. 키를 출력하지 않으며 별도 임시 계정 DB와 in-process TestClient로 실제 `/api/query` → `/api/output` → `/api/output/edit`를 호출합니다. 각 실행은 새 출력 폴더를 사용하는 것을 권장합니다. `--case bok-line`으로 한 사례만 실행할 수 있습니다.

## 판정과 한계

- 데이터 준비: 실제 조회·분류·계열 수 확인. 관측값이 없으면 실패로 기록합니다.
- 명령/출력: HTTP 상태, 모델 호출별 토큰/시간, 적용 명령, 기본 그래프 종류/패널 분할과 렌더러 trace를 기록합니다. 자동 조건이 실패하면 종료 코드 2를 반환합니다.
- 패널 판정은 보고서 설정 이름이 아니라 실제 trace의 축 쌍 개수로 검사합니다. 모델이 판독한 `reference_style`의 종류·영역 수·열 수는 명령 정규화에서 검증하며 현재 계열 수와 다르면 그룹 구분을 요청합니다.
- 통계 계약: 편집 전후의 지표·단위·주기·모든 시점/값을 비교하고, 서버 원행의 SHA-256을 따로 확인합니다. 실패 시 기존 출력이 그대로인지 확인합니다.
- 외관: `visual_review=pending`은 성공 판정이 아닙니다. 참고 PNG와 `*-after.json`의 실제 Plotly 출력에서 색상·격자·범례·겹침·읽기 쉬움·패널 구조를 사람이 확인해야 합니다.
- 패널 사례는 현재 조회한 계열 수에 맞춰 형식을 적용합니다. 원 그림의 은행 그룹·그룹별 여러 곡선·장기평균을 새로운 관측값처럼 만들지 않습니다. 완전히 같은 그룹 구조가 필요한 경우 해당 데이터와 그룹 어댑터가 추가로 필요합니다.
- 모델 응답·usage·지연은 호출 시점에 따라 달라집니다. 모델의 내부 추론은 평가 자료에 기록하지 않습니다.

최초 실패·반복 호출의 재실패·수정 후 확인을 구분한 [작업 기록](../../../docs/implementation/2026-10-14-vlm-reference-harness.md)을 함께 확인하세요.
