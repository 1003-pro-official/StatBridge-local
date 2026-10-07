# StatBridge Golden v2

**ai-assisted · 사람 검수 대기본. 공식 승인본이 아닙니다.**

v1과 기존 end-to-end/v2를 수정하거나 점수를 합치지 않는 독립 평가 계열입니다.
공개 자료는 dev 30건, test 42건입니다. 비공개 18건의 질문·정답은 이 저장소에서 제작하지 않습니다.

| 모드 | dev | test | 평가 범위 |
|---|---:|---:|---|
| discovery | 10 | 14 | 표·계열 선택 / 역질문 / 미지원 |
| e2e | 12 | 18 | 실제 질의 API → 기간 확정 → 출력 API |
| output | 5 | 7 | 실제 조회 → 출력 API의 그래프·해석 |
| edit | 3 | 3 | 먼저 실제 생성한 출력 → 실제 수정 |

- [설계서](DESIGN.md): 정답 구조, 출처, 분리 기준, 실행 한계
- [신뢰성 보완](HARDENING.md): 단위 근거, 엄격한 그래프 검사, 역질문 의미 검수, 편집 문구 계약
- [사람 검수](review/GUIDE.md): 골든 정답 승인과 응답 해석 판정은 별도 작업
- [PM 제작 절차](PRIVATE_SPEC.md): 비공개 18건의 규격만 제공
- [Holdout 인계 도구](holdout_support/README.md): 고정 도구·중복 제외 목록·승인 차단·합성 테스트. 실제 비공개 사례는 포함하지 않음
- [UI 정합성 수정](UI_REVISION.md): 교체된 18건과 독립 질문으로 수정한 6건
- source_inventory.json: 후보 5종의 분포, 채택 연구 결과물 14개, 제외 사유
- candidate_probes.json: 미채택 연차·지급결제 원본 탐색 및 제목 확인 여부
- dataset_manifest.json: 공개 사례·fixture·도구의 재현 해시
- .gitattributes: Git 줄바꿈 변환을 막아 기록된 바이트 해시를 체크아웃에서도 보존
- pilot.jsonl: 최종 72건에 포함되는 대표 12건
- [Jupyter 검토 노트북](notebooks/review.ipynb): 사례 필터, 정답·관측·그래프·근거 비교, 실패 코드와 구현 코드 탐색

## Jupyter에서 살펴보기

notebooks/review.ipynb를 열고 위에서부터 실행합니다. CASE_ID를 바꾸면 다른 사례를 볼 수 있습니다.
기본 동작은 저장된 관측 읽기이며 API 재실행·사람 승인 변경은 하지 않습니다.
UI 정합성 수정 후 전체 관측(ui-dev-test)을 기본으로 읽습니다.
OBSERVATION_SET을 pilot-ui로 바꾸면 새 대표 12건을 확인합니다. 미포함 사례는 미실행이며 실행을 합치지 않습니다.
기존 Python 환경의 pandas, plotly, jsonschema 외에 Jupyter 실행에는 ipykernel과 nbformat이 필요합니다.
Jupyter 커널은 프로젝트 가상환경을 선택하세요.

커널 없이 코드 셀을 확인하고 출력이 포함된 로컬 미리보기를 생성할 수도 있습니다.

~~~powershell
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/check_notebook.py --preview
~~~

results/review-preview.ipynb는 실제 Python 셀 실행 결과를 포함합니다.
Jupyter 커널을 통한 실행은 아니며 결과 파일이 없어도 관측을 만들어 채우지 않습니다.
출력 포함본은 results/에서만 관리하고, 원본 노트북은 셀 출력을 비운 상태로 관리합니다.

## 실행

저장소 루트에서 PowerShell로 실행합니다. 서비스 공개 API 변경은 없습니다.

~~~powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/validate.py --verify-sources
.venv/Scripts/python.exe -m pytest -q eval/statbridge-golden/v2/tests
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/run.py eval/statbridge-golden/v2/pilot.jsonl --output results/pilot-ui.jsonl
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/score.py eval/statbridge-golden/v2/pilot.jsonl eval/statbridge-golden/v2/results/pilot-ui.jsonl --output eval/statbridge-golden/v2/results/pilot-ui-score.json
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/run.py eval/statbridge-golden/v2/dev.jsonl --output results/dev-ui.jsonl
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/run.py eval/statbridge-golden/v2/test.jsonl --output results/test-ui.jsonl
~~~

score.py는 각 split에 대해 별도로 실행합니다. output/edit/e2e 자동 검사 통과도
해석 검수가 없으면 pending_review이며 성공에 포함하지 않습니다.
discovery 통과는 자동 진단 통과이지, 미승인 골든셋의 공식 평가 점수가 아닙니다.
역질문 선택지 의미가 확정되지 않으면 discovery도 pending_review로 분리합니다.
review_packet.py는 기존 검수 파일을 덮어쓰지 않으므로 실행별 새 이름을 사용합니다.

~~~powershell
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/review_packet.py eval/statbridge-golden/v2/dev.jsonl eval/statbridge-golden/v2/results/dev-ui.jsonl --output results/dev-ui-review.jsonl
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/score.py eval/statbridge-golden/v2/dev.jsonl eval/statbridge-golden/v2/results/dev-ui.jsonl --reviews eval/statbridge-golden/v2/results/dev-ui-review.jsonl --output eval/statbridge-golden/v2/results/dev-ui-reviewed-score.json
~~~

실서비스 검증은 명시적으로 --live를 추가합니다. KOSIS/NCP 설정이 필요하며 비용이 발생할 수 있습니다.
기본 live는 로컬 실제 앱의 ASGI 경로와 실제 공급자를 사용하고 요청 파라미터를 관측합니다.
--base-url을 지정하면 외부 실행 API를 호출하지만 해당 API가 전체 항목·분류 ID를 노출하지 않아
수치 계열 식별은 unobserved입니다. 정답으로 빈 식별자를 보충하지 않습니다.

재제작에는 openpyxl, pypdf가 설치된 Python과 기존 research 원본 및 로컬 CSV가 필요합니다.
UI 수정은 scripts/ui_revision.py로 재현하며, 현재 개정본에는 다시 적용하지 않습니다.
기존 author.py는 첨부 기반 초판 제작 도구이므로 현재 공개 세트를 덮어쓰지 못하도록 차단했습니다.
scripts/probe_sources.py는 미채택 보고서의 원본 확인 기록을 재현합니다.
마지막에 저장소 가상환경으로 scripts/manifest.py를 실행합니다.
ui_revision.py는 지원 계열의 CSV를 식별자·분류·기간으로 다시 추출하며 v1 질문이나 정답을 읽지 않습니다.
원본이 없는 배포 환경에서는 이미 제공된 최소 fixture로 오프라인 실행하고,
원본 검증 경고와 수치 fixture 검증을 구분합니다.

실행 예측, 검수 결과 및 평가 결과는 results/에만 저장하며 Git에서 제외합니다.
키·원자료 전체·벡터 DB·비공개 자료는 반입하지 않습니다.

기존 첨부 사례 18건은 internal/components/에 보존했습니다. 공개 72건과 점수를 합치지 않습니다.
루트 attachment_registry.json과 *-input.json은 초판 재현용 유산이며 새 공개 input에서는 참조하지 않습니다.
오프라인 편집 명령 재생은 자연어 편집 분류 성능이나 실제 브라우저 조작 검증을 의미하지 않습니다.
