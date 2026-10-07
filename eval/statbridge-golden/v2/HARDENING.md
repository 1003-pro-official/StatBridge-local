# v2 평가 신뢰성 보완

이 문서는 UI 정합성 수정 전의 보완 기록입니다. 현재 공개 사례·실행 경로는
[UI_REVISION.md](UI_REVISION.md)를 따릅니다. 아래 첨부 사례 ID는 내부 보존본에 해당합니다.

ai-assisted. 정답 및 해석에 대한 사람 승인을 대신하지 않습니다.

## 보완 범위

- DT_514Y001/002/003의 누락된 CSV 단위와 평가용 표시 단위를 구분합니다. unit_rules.json에 원본 단위, 지수 표시 규칙, 배율 1, 공식 산식의 URL·파일 해시·페이지를 기록합니다. 숫자는 바꾸지 않습니다.
- 관련 5사례에 단위 정의의 출처를 추가합니다. 표기 '지수'는 CSV에서 읽은 UNIT_NM이라고 주장하지 않는 평가용 규칙입니다. 공식 산식으로 의미를 확인했으나 여전히 사람 검수 대상입니다.
- SBV2-0064의 전월 변화량 누적합은 '조원'과 시작·종료 시점이 포함된 누적 변화량 이름으로 기록합니다. 원본 입력의 단위·이름·값은 유지합니다.
- 비어 있는 단위, 근거 없는 단위 정규화, 누락되거나 다른 입력 해시를 차단합니다.
- 알 수 없는 공급자가 KOSIS 계열로 가장하는 경우, 값 필드 누락을 명시적 null로 취급하는 경우, 무한대·NaN 허용 오차도 차단합니다.
- 선그래프의 실제 선 표시 모드와 숨겨진 선을 검사합니다. Plotly에서 mode를 생략한 정상 기본 표현은 허용합니다.
- 역질문은 공백 정규화 후 정확한 허용 선택지를 자동 확인합니다. 허용 단어만 포함한 긴 문장은 의미 일치를 확정하지 않고 clarification_semantics_unreviewed로 검수 대기 처리합니다. 명백히 다른 선택지·누락은 실패입니다.
- 현재 골든셋에 사용된 역질문 항목 조합을 명시적 어휘 계약으로 관리합니다. 새 조합은 정답 근거와 계약을 함께 검토해야 합니다.
- 편집 지시는 edit_contract.py의 제한된 문구 계약과 구조화 명령을 비교합니다. 다른 제목·기간·변환, 지원하지 않는 문구, 추가 명령 필드는 차단합니다.

## 평가 범위를 혼동하지 않기

편집 문구 계약은 평가 자료의 정합성 검사이며 제품의 자연어 파서가 아닙니다.
오프라인 실행의 ReplayCommand는 여전히 input에 제공된 명령을 적용합니다.
따라서 edit 자동 통과는 명령 적용 검사이지 자연어 해석 성공이 아닙니다.

역질문 의미가 검수 대기이면 automatic_pass는 false입니다.
review_packet.py에서 만든 새 검수 파일의 clarification_options_correct를 사람이 true/false로 판정합니다.
reviewer, human_approved, prediction_sha256이 현재 응답과 맞아야 적용됩니다.
사람 검수로 해소된 역질문도 자동 검사 통과로 다시 집계하지 않습니다.
기존 출력 해석의 facts_correct 등 네 항목은 계속 별도로 요구합니다.

review_packet.py는 기존 검수 파일을 덮어쓰지 않습니다. 새 실행마다 새 파일 이름을 사용하세요.
정답 승인과 응답 검수는 별개이며 승인 여부를 자동으로 올리지 않습니다.

## 원본 확보 및 검증

지수 산식 근거는 한국은행 작성 금융기관 대출행태조사 통계정보 보고서의
[공식 통계청 공개 원본](https://kostat.go.kr/boardDownload.es?bid=12030&list_no=351218&seq=3)입니다.
PDF 16쪽(인쇄 13쪽)을 확인했습니다. 원본 전체는 Git 제외 results/source-originals에만 보관합니다.
복제 환경에서는 해당 URL의 파일을 아래 위치로 공급한 뒤 해시를 확인하세요.
파일이 없으면 일반 검증은 원본 미관측 경고, --verify-sources는 오류로 보고합니다.

~~~powershell
New-Item -ItemType Directory -Force eval/statbridge-golden/v2/results/source-originals
Invoke-WebRequest -Uri 'https://kostat.go.kr/boardDownload.es?bid=12030&list_no=351218&seq=3' -OutFile eval/statbridge-golden/v2/results/source-originals/lending-survey-definition.pdf
Get-FileHash eval/statbridge-golden/v2/results/source-originals/lending-survey-definition.pdf -Algorithm SHA256
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/validate.py --verify-sources
~~~

예상 원본 해시는 unit_rules.json에 있습니다. 파일이 달라지면 자동으로 새 해시를 받아들이지 않습니다.
오프라인 숫자 실행에는 해당 PDF나 외부 조회가 필요하지 않습니다.
독립 원본 대조는 openpyxl·pypdf가 설치된 Python으로 self_audit.py --scope sources를 실행합니다.

## 기존 내용 보존

harden_dataset.py는 변경 전 사례·fixture·claims·manifest를 results/before-hardening-*에 백업합니다.
사람 승인본이 있으면 마이그레이션을 거부합니다. 기존 사람 검수 양식은 수정하지 않습니다.
prepare_notebook.py는 실행 출력이 포함된 노트북을 바이트 단위로 동일하게 results/review-working-*에 보존한 후 배포본의 출력만 비웁니다.
질문, 코드 셀 내용, 기존 사용자 수정과 v1은 보존합니다.
출력 있는 검토 작업은 보존된 작업본이나 check_notebook.py --preview로 만든 results/review-preview.ipynb에서 계속할 수 있습니다.

## 남은 단계

이번 보완은 정답 근거와 검증·채점 신뢰성에 집중합니다.
후속 대화의 실제 상태 재현, 편집 조회 계측, 실행 시작 시 전체 해시 고정,
자연어 편집 평가 분리, 전체 72건 새 실행 및 실패 원인 분류는 다음 단계입니다.
기존 관측의 재채점과 새 실행 결과는 파일 이름으로 구분하며, 새 실행하지 않은 결과를 최신 서비스 성능이라고 표시하지 않습니다.
공식 승인에는 사람의 정답 검토 및 응답 해석 검수가 필요합니다.
