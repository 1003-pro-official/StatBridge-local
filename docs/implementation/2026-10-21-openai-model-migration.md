# Sol / Luna 역할별 모델 교체 (2026-10-21)

ai-assisted. 사용자가 첨부 제안에 따라 교체와 검증을 요청하여 A·B를 적용했다. 계획까지 Luna로 낮추는 C 단계는 적용하지 않았다. local1과 StatBridge1에 같은 코드·테스트·문서를 반영하고, 각 폴더 .env의 모델 두 값만 변경했다.

## 실제 호출 경로

| 역할 | 모델 / 설정 |
|---|---|
| 파생 계획, 경제학적 의미 검토 | `OPENAI_CHART_MODEL=gpt-6.1-sol` |
| 이미지·PDF 차트 편집 | 같은 strong client |
| 보고서 대화, 기존 질문 API, 보고서 캡션·초안 | 같은 strong client |
| 출력 요약의 fact ID 선택, 차트 스타일 제안 | `OPENAI_TEXT_MODEL=gpt-6-luna` |
| NCP 언어 해석·임베딩 | 기존 구성 유지 |

`bridge_api.py`의 계획 모델 하드코딩을 제거했다. `report_client`를 별도로 두어 보고서까지 Luna로 내려가는 것을 막았다. `OPENAI_TEXT_MODEL`이 없거나 빈 값이면 strong 모델을 이용한다. `store:false`, 기존 프롬프트의 수치·인용 제한, 표현식 트리·단위 검증, 의미 검토, 폴백, 계정별 검증 계획 캐시를 유지했다. 모델이 바뀌면 파생 계획 캐시를 다시 검토해야 하는 회귀 테스트를 추가했다.

Responses PDF는 `input_file.detail=low`, 출력 토큰 하한은 reasoning을 포함해 4,096으로 변경했다. reasoning `low`는 두 대상 모델이 지원하는 값이다. 역사적 GPT-5.4 evidence는 재작성하지 않았다. 기존 검증 도구 두 개의 기대 모델을 인자로 받을 수 있게 하되 기본값은 해당 과거 실험의 GPT-5.4로 남겼다.

## 실제 공급자 검증

두 모델 모두 기존 키로 실제 JSON 응답을 받았다. 아래는 작은 개발 스모크이며 장기간·전체 파생지표의 품질 동등성 평가가 아니다.

| Sol 스모크 | 결과 | 초 |
|---|---|---:|
| 생산자물가지수 총지수 역수 계획·의미 검토 | approved, Sol 2회 | 14.054 |
| 실제 KOSIS 관측 조회 | org 301 / DT_404Y014, API 4행 | 0.981 |
| 이미지 참고 색상 편집 | set_series_color, 원자료·표 값 유지 | 8.858 |
| PDF 참고 색상 편집 | set_series_color, 원자료·표 값 유지 | 10.502 |
| 근거 기반 보고서 초안 | grounded_model_draft | 7.475 |

실제 원자료 4행과 최종 역수 노드를 Decimal로 별도 검산하여 오차 1e-12 미만을 확인했다. 이미지/PDF는 단순 합성 선 그림이며 밀집된 여러 쪽 보고서의 판독률을 검증한 것은 아니다. 5개 스모크 모두 90초 미만이며 소표본의 최댓값은 14.054초다. 같은 질문의 GPT-5.4 계획·검토도 성공(7.377초)했다. Sol의 속도 향상이나 전체 성공률 동등성을 주장하지 않는다. 첫 경제심리지수 스모크는 API 응답 단위를 확정하지 못하여 계산을 차단했으며 원자료를 임의 보완하지 않았다.

`tools/evaluate_model_roles.py`의 합성 개발 30건으로 Luna를 실제 호출했다. 월·분기·연간, 1~3계열, 5개 단위, 상승·하락·정체·전환 패턴과 선/막대 요청을 포함했다.

- 요약 fact 선택: 30/30, rules 폴백 0% (<5%). 서버의 ID·계열 완전성·비교 순서 검증을 통과한 결과만 합격이다.
- 차트 유형과 명시 제목 일치: 29/30 (96.7%, 기준 90% 이상). 30/30으로 표기하지 않는다.
- 합성 개발 입력이며 비공개 holdout 정답이나 사용자 저장 분석을 사용하지 않았다.
- 제안의 혼합 1,000건 비용 61% 절감은 가정 기반 추정이다. 이번 검증으로 실청구 절감률을 확정하지 않는다.

## 실제 UI에서 추가로 발견한 호환성 보완

보고서 대화 계획기는 “스키마대로”라는 지시만 전달하고 실제 `ReportPlan` 스키마를 전달하지 않았다. 새 모델의 자유형 응답이 검증에서 거절되는 것을 실제 UI에서 확인하여, 사용자 질문·이전 대화·계열 메타데이터와 함께 서버의 실제 스키마를 제공하도록 보완했다. 수치 계산과 답변은 계속 서버에서 수행하며 임의 계산식·알 수 없는 계열은 거절한다. 이 보완은 제안의 단순 모델명 변경 외에 UI 검증 중 필요한 최소 호환성 수정이다.

## 회귀와 적용 검증

- 전체 오프라인 pytest: 처음 수집된 테스트에서 2,246 PASS / 1 FAIL / 355 subtests PASS, 864.27초. 실패는 보고서 mock이 이전 `output_agent.ncp_client`에 주입되어 새 `report_client`의 장애를 검사하지 못한 한 건이다. 새 경계에 주입하도록 테스트 4개 파일을 갱신했다.
- 관련 최신 코드 재검사: local1 70 PASS (보고서·캐시·역할), 스키마 보완 후 보고서·역할 29 PASS. StatBridge1 관련 검사 140 PASS, 최종 스키마·캐시·역할 45 PASS. 이 수치를 전체 검사와 더해 중복 건수를 부풀리지 않는다.
- 두 폴더 `validate_v41.py` PASS. 비공개 정답 경로는 전달하지 않았다.
- 두 폴더 TypeScript/Vite 빌드 PASS. 프런트 소스 변경은 없다. 기존 큰 번들 경고는 남아 있다.
- 두 실제 백엔드 재시작 후 8000/8001 health 200, 승인 표 349개를 확인했다.
- local1 UI에서 실제 파생 계산·산식·출력과 실행 로그의 Sol planning/semantic_review 두 호출을 확인했다. 해당 trace를 Langfuse에서 `fields=basic,model,usage`로 읽어 Sol generation 두 건의 수신을 확인했다. 기본 목록 응답은 model 필드를 생략하므로 명시적으로 요청해야 한다.
- StatBridge1 기본 금리 조회는 기존 빠른 출력 경로에서 모델 0회로 완료되었다. Luna 호출을 증명하기 위해 불필요한 UI 호출을 강제로 추가하지 않았다. Luna 실제 공급자 검증은 위 개발 30건이다.

런타임 상세 결과·토큰·계산 evidence는 각 폴더의 무시된 `.venv/cache/model-migration-20261021/`에 둔다. 키·계정 DB·원자료·생성 평가 결과는 커밋하지 않는다.

## 롤백

Luna만 해제하려면 각 폴더 `.env`의 `OPENAI_TEXT_MODEL`을 지우거나 비우고 백엔드를 재시작한다. GPT-5.4 단일 구성으로 돌아가려면 `OPENAI_CHART_MODEL=gpt-5.4`, `OPENAI_TEXT_MODEL=`로 설정한다. 두 환경변수를 모두 삭제하면 새 코드의 기본 Sol이므로 GPT-5.4로 돌아가지 않는다.

## 공식 문서

- [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [PDF detail](https://developers.openai.com/api/docs/guides/file-inputs#pdf-detail-levels)



## 최종 UI·보존 확인

스키마 보완 후 StatBridge1에서 동일 질문 “현재 그래프의 변화를 보고서 문장으로 설명해줘.”가 Sol 해석 1회로 정상 답변하였다. “그중 가장 많이 하락한 것은?”은 이전 대상과 시작 대비 기준을 이어받아 GPT 0회로 수신금리 0.25%p 하락을 출력하였다. 존댓말 대화 안내와 달리 보고서 본문은 이다/하였다 문체이며 수치는 최신 서버 원자료로 검산한다.

계정·저장 분석은 local1 users=5/graphs=9, StatBridge1 users=4/graphs=5로 전후 동일하다. 모델 두 키를 제외한 .env 파싱 값의 SHA-256도 전후 동일하다. 데이터·포트·기존 비밀 값은 동기화하지 않았다.
