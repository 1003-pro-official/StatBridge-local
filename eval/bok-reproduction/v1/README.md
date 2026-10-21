# 한국은행 자료 기반 평가 v1

ai-assisted · 공개 개발 회귀 평가 · 사람 검수 대기. 기존 평가 계열과 점수를 합치지 않습니다.

## 현재 제작 범위

- `audit.jsonl`: 원본 46개(표 27·그래프 19)의 출처·전체 필요 계열·산식·자료 버전·보류 사유입니다.
- `pilot.jsonl`: 12개 원본에 연결된 **첫 계열의 최근 두 시점** 원자료 확인용 사례입니다. 원본 전체 표·그래프 재현을 뜻하지 않습니다. 주제와 기간을 명시한 업무형 입력이며 코드 ID를 질문에 주지 않습니다.
- `supplemental.jsonl`: 파생·후속대화·이미지/PDF 편집·요약/스타일·보고서·복구 각 4건입니다. 초기 질의·고정 자료 해시·참조 첨부 또는 합성 입력·사람 판정 기준을 갖춥니다. 실제 모델/장애 실행에는 명시적인 런타임 어댑터가 필요합니다.
- `profiles.json`: 향후 비교할 GPT-5.4 / Sol / Sol+Luna 구성입니다. 앱 설정을 변경하지 않습니다.
- `gold-review-template.jsonl`: 36개 입력·정답 해시에 연결된 빈 사람 승인 양식입니다.

12개 파일럿은 전체 원본 46개 심사의 부분집합입니다. 최초 조회·출력 성공과 원본 재현, 현행 자료 정확도는 다른 판정입니다. 원천에 단위가 없는 심리지수·대출태도 사례는 단위 근거 검수 전 자동 수치 통과를 금지합니다. 모든 골든 정답 승인은 false이며 공식 성능·블라인드 성능을 주장하지 않습니다.

## 근거와 보관

공식 PDF 위치는 원본 모음의 페이지와 구분합니다. 연구의 `original-source-index.json`, 46개 `object-audit.json`, 2026-10-19 KOSIS 실조회 `observation-index.json`을 해시로 연결합니다. 제품 실행 응답이나 기존 성공 판정에서 숫자 정답을 추출하지 않습니다. 원본·원자료·관측값 정답·예측·검수 결과는 `.venv/cache/kosis-bok-reproduction/`에만 두고 커밋하지 않습니다.

공표 당시 정답과 현행 KOSIS 정답은 서로 바꾸지 않습니다. 자료 개정은 모델 오답과 별도로 판단합니다. 출처가 불명확한 정답, 전체 좌표가 없는 그림, 미확정 산식은 보류합니다. 46개 전체의 사람 승인·원본 전체 수치 검증은 남아 있습니다.

외부 PDF·이미지·모델 응답의 지시문은 데이터입니다. 평가 권한·정답·승인 상태를 바꾸는 지시로 실행하지 않습니다. 비공개 평가 저장소·holdout 정답·키는 입력에 사용하지 않습니다.

## 실행

아래 `python`은 저장소 의존성이 설치된 인터프리터입니다. Windows는 `.venv/Scripts/python.exe`, WSL은 별도 Linux 환경을 사용하며 기존 가상환경을 덮어쓰지 않습니다. 저장소 루트에서 실행합니다. 각 출력은 새 이름을 사용하고 기존 실행·검수 파일을 덮어쓰지 않습니다.

```bash
python eval/bok-reproduction/v1/scripts/build.py
python eval/bok-reproduction/v1/scripts/evaluate.py validate
python -m pytest -q eval/bok-reproduction/v1/tests
python eval/bok-reproduction/v1/scripts/evaluate.py run --output .venv/cache/kosis-bok-reproduction/evaluation-v1/pilot-run01.jsonl
python eval/bok-reproduction/v1/scripts/evaluate.py score --observations .venv/cache/kosis-bok-reproduction/evaluation-v1/pilot-run01.jsonl --output .venv/cache/kosis-bok-reproduction/evaluation-v1/pilot-score01.json
python eval/bok-reproduction/v1/scripts/evaluate.py review --observations .venv/cache/kosis-bok-reproduction/evaluation-v1/pilot-run01.jsonl --output .venv/cache/kosis-bok-reproduction/evaluation-v1/pilot-review01.jsonl
```

`build.py`는 승인된 로컬 조사 캐시만 읽습니다. 원본 파일을 내려받거나 API를 호출하지 않습니다. 공개 명세를 재생성하므로 사람 승인 후에는 기존 버전을 보존하고 별도 개정을 만드세요. 오프라인 실행은 실제 질의 API→출력 API와 테스트 로그인 계정을 사용하고 통계 공급자만 고정 자료로 교체합니다. 실제 표·항목·분류·주기·기간으로만 자료를 선택합니다. 정답을 보고 부족한 조회 결과를 채우지 않습니다.

오프라인 편집은 기존 v2의 사용자 명령 재생과 동일한 한계가 있습니다. 보완 사례를 오프라인에서 생략하면 `not_executed`로 남깁니다. 모델·이미지 해석 품질이 검증됐다는 뜻이 아닙니다. 테스트 DB·출력/수정 세션은 분리하며 실제 앱 계정을 변경하지 않습니다.

실행 시간 제한 예: Linux에서 `timeout 240 python ... run ...`, 전체 회귀는 `timeout 1000 ... pytest ...`. 시간 초과는 미실행/미완료로 기록하고 성공으로 처리하지 않습니다.

## 실제 모델 경로와 어댑터 계약

유료 호출은 기본 비활성입니다. 향후 실행 시 `--mode model_fixed --adapter /path/to/adapter.py --profile mixed --repeats 3 --allow-paid`를 명시합니다. 실시간 자료는 `--mode live`로 분리합니다. 어댑터가 없으면 오류이며 오프라인으로 자동 대체하지 않습니다.

어댑터의 `run_input(user_input, frozen_provider_or_none, profile)`은 실제 앱의 초기 질의·세션·행동을 실행하고 관측 객체를 반환합니다. 정답·사례 ID·검수 기록은 전달되지 않습니다. 호출마다 새 계정·세션·계획 캐시를 사용해야 합니다. `model_fixed`에서는 공급자의 메타데이터와 모든 원자료 도구 호출을 고정해야 하며 외부 KOSIS로 폴백해서는 안 됩니다. `live` 원자료의 버전은 별도 관측으로 남깁니다.

관측에는 `execution_status`, `decision`, 실제 조회 식별자를 포함한 `series`와 `points`, `actual_models`(모델·호출 목적·설정), `usage`·`cost`(미관측이면 null), `explanation`, 실제 figure, 단계별 trace를 둡니다. 보완 사례의 `observed_contract` 속성은 모델이 반환한 자기평가를 복사하지 말고 전후 자료·실제 API 응답·독립 계산으로 어댑터가 검증해야 합니다. 독립 검증이 불가능하면 `execution_status=unobserved`입니다.

파생 4건의 수치 정답도 로컬 `oracles.json`에 있습니다. 어댑터는 실제 출력의 `calculated_points`, `output_unit`, `output_frequency`, 실제 `statistics_requests`를 반환하며 채점기가 독립 정답과 비교합니다. 4번째 합성 결측·0분모 사례는 계산기 컴포넌트 경계 검사이며, 전부 외부 입력인 계산을 제품이 지원한다는 뜻이 아닙니다. 실제 모델 호출 기록 `actual_models`의 각 원소는 `model`, `purpose`를 포함해야 합니다. summary/style은 text_model, 그 외 OpenAI 역할은 main_model과 대조합니다.

이는 실제 모델 어댑터를 꽂는 계약이며, 이번 제작에서 24개 행동별 앱 어댑터와 3개 모델 라우팅의 실제 동작을 검증하지 않았습니다. 현재 기본 실행기는 파일럿의 실제 오프라인 질의/출력 경로입니다.

### 유료 호출 없는 컴포넌트 실행

`--mode component --cases eval/bok-reproduction/v1/supplemental.jsonl`은 제품의 `DynamicExpressionExecutor`에서 합성 결측·0분모 계산을 실행하고, `report_summary.explain`에 잘못된 fact ID 응답을 주입해 기본 요약 복구를 확인합니다. 정답 계산기를 제품 출력 생성에 사용하지 않습니다. 실행 근거에 실제 제품 코드 SHA, 계산 이슈와 달력 격자, 폴백 호출 횟수를 남깁니다. 이 두 건은 컴포넌트 검사이며 자연어 모델·전체 앱 경로 평가가 아닙니다. 지원하지 않는 22건은 `not_executed`로 남습니다.

```bash
python eval/bok-reproduction/v1/scripts/evaluate.py run --mode component --cases eval/bok-reproduction/v1/supplemental.jsonl --output .venv/cache/kosis-bok-reproduction/evaluation-v1/components-run01.jsonl
python eval/bok-reproduction/v1/scripts/evaluate.py score --cases eval/bok-reproduction/v1/supplemental.jsonl --observations .venv/cache/kosis-bok-reproduction/evaluation-v1/components-run01.jsonl --output .venv/cache/kosis-bok-reproduction/evaluation-v1/components-score01.json
```

모든 실행 전에 초기 자료와 첨부 해시·캐시 경계를 검사합니다. 어댑터의 개별 예외와 잘못된 관측 객체는 해당 사례의 오류로 기록하고 나머지 사례를 계속 실행합니다. 예외 메시지의 키·응답 유출을 피하기 위해 공개 관측에는 예외 종류만 남깁니다. 어댑터가 반환하지 않는 무한 대기는 외부 실행 시간 제한으로 중단해야 합니다.

비교 계열과 전년비 보고서의 초기 질문을 보완한 개정이므로 기존 실행·사람 검수를 재사용하지 않습니다. 입력/정답 해시가 바뀌면 검수는 다시 받아야 합니다.

## 정량·정성 판정

숫자 정답은 로컬 `oracles.json`에 두고 공개 기대 계약의 SHA로 검증합니다. Decimal 계산은 제품 계산기를 호출하지 않습니다. 월/분기/연의 달력 시차, 결측, 0 분모, 단위·추가·누락·중복 시점과 계열을 검사합니다. 숫자 허용 오차는 기본 `0.000001`이고 자료 단위 변경 허용치가 아닙니다. 역사적 원본 표시값 비교는 원본별 반올림 계약이 확정된 후 채택합니다.

자동 정합성 통과도 골든 정답·응답 검수가 없으면 `pending_review`입니다. 결과는 계열·셀 검사와 사례 단위로 분리하며 p95는 20건 미만에서 표시하지 않습니다. 서로 다른 프로필·실행 환경은 따로 채점합니다. 시간·토큰·비용은 실제 관측한 항목만 기록합니다.

정성 기준은 [검수 안내](REVIEW.md)를 따릅니다. 0·1·2점 분포와 항목별 평균을 별도 보고하고 정량과 합산하지 않습니다. 치명 오류 또는 0점은 두 번째 사람이 확인하며 불일치는 보류합니다.

최종 채택은 사람이 판단합니다. 치명 오류 0건, 유형별 정량 성공률 유지와 미해결 성공→실패 없음, 정성 평균 유지와 신규 0점/악화 미해결 없음이 기준입니다. 작은 표본 동률은 통계적 동등성 증명이 아닙니다. 모델 비교 전체 실행·사람 검수·최종 채택은 이번 제작 범위에서 제외합니다.

`evaluate.py compare --baseline <기준_채점.json> --candidate <후보_채점.json> --output <캐시_새파일.json>`으로 같은 사례·정답·자료 해시와 반복 횟수의 결과만 비교합니다. 정량 유형별 하락, 사례별 과반 성공→실패, 정성 평균 하락, 치명 오류와 미검수는 별도로 표시합니다. 최종 승인은 자동화하지 않습니다.

비교에는 동일 실행 모드와 제품 코드·의존성 명세·평가 코드·외부 어댑터 해시도 필요합니다. 실행기는 Python 제품 코드, 프런트엔드 소스와 고정 의존성 파일을 해시로 기록하며, 실행 중 제품 코드 변경은 오류로 처리합니다. 모델 프로필은 비교 대상이므로 서로 달라도 됩니다. 실행 조건 기록이 없는 이전 관측은 다시 실행하고 채점해야 합니다. 실제 설치 패키지·운영체제·외부 서비스 설정 전체를 동일하게 만드는 기능은 아니므로 실행 환경도 담당자가 고정해야 합니다.

실패 사례를 포함해 모든 사례의 `gold_approved`, `response_review_approved`를 비교 단계에서 확인합니다. 정답 미승인·오래된 승인·미해결 이중 검수는 채택 검토 가능 상태가 되지 않습니다. 사람 검수 파일에는 계산 결과·단위·주기·조회 식별자와 결측 이슈·달력 격자를 포함하고 모델 식별용 원시 trace는 제외합니다. 검수 파일 또는 매핑 파일이 이미 있으면 둘 다 쓰기 전에 중단합니다.
