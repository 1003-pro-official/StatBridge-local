# v2 Holdout 제작 인계 패키지

ai-assisted. 이 패키지는 도구·규격만 담으며 실제 비공개 사례와 사람 승인은 0건입니다.
현재 공개 환경에서 비공개 저장소를 열거나 내려받지 않습니다.

## 공개 단계

저장소 루트에서 새 출력 이름을 사용합니다. 기존 인계본은 덮어쓰지 않습니다.

```powershell
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/prepare_holdout.py --output results/holdout-kit-001
.venv/Scripts/python.exe eval/statbridge-golden/v2/results/holdout-kit-001/synthetic_smoke.py --product-root .
```

bundle-manifest.json은 도구·스키마·중복 제외 목록의 해시와 공개 데이터 버전을 고정합니다.
공개 질문·정답·수치 fixture·개발 대화·제품 실패 결과는 패키지에 포함하지 않습니다.
중복 제외 목록은 공개 연구 결과물 ID, 원본 해시/위치, 계열-시점의 해시만 포함합니다.
단위 정의 등 공통 방법론 문서의 재사용은 그림 중복으로 취급하지 않습니다.
feature-contract.json은 지원 API·출력·기간과 평가 경계를 기록합니다.
합성 테스트는 가짜 API transport와 실제 OutputAgent/채점기를 검사하며 제품 성능은 아닙니다.

## 비공개 작업으로 전환

사람이 기존 비공개 저장소를 별도 작업 폴더로 열고 운영 규칙부터 확인합니다.
기존 v4.1 holdout/정답은 열거나 검색하거나 재사용하지 않습니다.
전용 브랜치는 eval/statbridge-golden-v2-holdout입니다. 공개 환경에서 이 전환을 대신하지 않습니다.
패키지를 tools/statbridge-v2-kit/에 배치하고, 표시된 manifest 해시를 PM이 확인합니다.
adapter.py는 지정된 비공개 origin과 전용 브랜치가 아니면 사례를 읽기 전에 중단합니다.
이 검사는 사고 방지 장치이며 접근 권한·격리를 대신하는 보안 장치는 아닙니다.

평가 도구에는 jsonschema, pandas, plotly, fastapi, httpx와 제품의 Python 의존성이 필요합니다.
제품 소스와 data/processed 메타데이터, research 마스터 및 검증 원자료는 별도 고정 제품
체크아웃에 준비합니다. 제작 담당에게 구현 코드와 실패 결과를 읽도록 제공하지 않습니다.
Python 실행 환경에서 제품을 import하는 것과 제작 프롬프트로 구현을 읽는 것은 구분합니다.

```powershell
python tools/statbridge-v2-kit/adapter.py init --workspace .
```

이 명령은 statbridge-golden/v2/에 빈 cases.jsonl, 스키마, 빈 registry/provider를 준비합니다.
기존 디렉터리나 v4.1 자료는 덮어쓰지 않습니다. 실제 사례를 생성하거나 승인하지 않습니다.

## 제작과 검수

목표: discovery 6(선택 3/역질문 2/미지원 1), e2e 8(단일 6/복수 2),
output 3(line combined/bar combined/line separate), edit 1(제목 변경).
ID는 SBV2-H0001~H0018, split은 holdout입니다.
research 원본을 먼저 선정·검증하고 독립 질문을 작성합니다. 업로드·이전 대화 유지는 가정하지 않습니다.
같은 연구 결과물/그림 또는 같은 계열-시점이 공개 세트와 겹치면 제외합니다.
같은 표를 쓰는 것은 허용하지만 표현·기간만 바꾼 질문은 사람 검수에서 제외합니다.

사례에는 공개 v2와 같은 input/expected/evidence/review를 사용합니다.
fixtures/와 claims/는 최소 검증 자료만 담습니다. output/edit는 expected.data.source_fixture로
계산 원자료를 기록하며 input.data_fixture는 금지합니다. 실제 조회에서 출력·편집 세션을 받습니다.
series_registry는 정확한 식별자·단위·주기 계약을, fixtures/provider.json은 독립 추출한
고정 공급 자료를 담습니다. 원자료의 표시 단위를 추측하거나 요청 실패를 정답으로 덮지 않습니다.
원본 path는 고정 제품 체크아웃 기준입니다. 원자료 전체와 단위 정의 PDF는 별도 공급하며 커밋하지 않습니다.
unit_rules.json은 해당 원자료 위치/해시와 일치하도록 검토하고 고정합니다.
authoring_protocol.json에는 제작자의 구현 노출 여부를 PM이 boolean으로 명시합니다.

```powershell
python tools/statbridge-v2-kit/adapter.py validate --workspace . --product-root <제품체크아웃> --partial
python tools/statbridge-v2-kit/adapter.py validate --workspace . --product-root <제품체크아웃>
```

partial은 작성 중 검사용이며 완료·실행 자격을 주지 않습니다. 완성본은 18건과 분포를 검사합니다.
원자료 숫자는 별도 재추출로 독립 검증합니다. 검증기는 추출의 독립성이나 인간 판정을 증명하지 않습니다.
PM은 질문·원본·수치·단위·주기·허용 답안·중복·독립 계산을 실제로 확인합니다.
case.review를 승인한 뒤 아래 명령으로 해시가 연결된 빈 승인 양식을 생성합니다.

```powershell
python tools/statbridge-v2-kit/adapter.py approval-template --workspace . --product-root <제품체크아웃>
```

review/gold-approvals.jsonl의 author/reviewer는 서로 달라야 합니다. 검수한 항목만 true로
기록하고 구현 노출 여부를 명시합니다. 해시를 변경해 승인 변경을 숨기지 않습니다.
사례가 바뀌면 이전 승인 항목을 무효화하고 실제 재검수 후 새 양식을 별도 보존합니다.
사람 승인을 자동 생성하지 않습니다. 부족한 근거로 18건을 채우지 않습니다.

## 고정과 오프라인 평가

제품 커밋은 PM이 지정합니다. src와 data/processed의 미커밋 변경이 있으면 고정하지 않습니다.
도구·정답·fixture·공급자·승인·제품 코드/메타데이터를 release.json에 고정합니다.

```powershell
python tools/statbridge-v2-kit/adapter.py freeze --workspace . --product-root <제품체크아웃> --product-commit <PM지정커밋>
python tools/statbridge-v2-kit/adapter.py run --workspace . --product-root <제품체크아웃> --run-id offline-001
python tools/statbridge-v2-kit/adapter.py review-packet --workspace . --product-root <제품체크아웃> --run-id offline-001
python tools/statbridge-v2-kit/adapter.py score --workspace . --product-root <제품체크아웃> --run-id offline-001
```

18건 승인·해시 고정 전 실제 후보 실행을 차단합니다. 실행 버전은 시작 전에 기록합니다.
실행/검수/채점 파일은 results/에만 저장하며 기존 파일을 덮어쓰지 않습니다.
공급자는 실제 요청 파라미터로 조회합니다. 단위·분류를 정답으로 보충하지 않습니다.
편집은 오프라인 명령 재생입니다. NCP 자연어 편집 분류 능력이나 브라우저 UI 검증이 아닙니다.
응답 해석 검수는 정답 승인과 별도로 수행하며 미검수는 pending_review입니다.
PM 검토 후 aggregate-report.json만 개발 담당에게 전달합니다. 상세 결과와 질문·정답은 전달하지 않습니다.
실서비스 실행 옵션은 이 어댑터에서 제공하지 않습니다. 키·비용 승인 후 별도 계획으로 진행합니다.
상세 피드백으로 개발에 사용한 세트는 이후 블라인드 holdout으로 주장하지 않습니다.
