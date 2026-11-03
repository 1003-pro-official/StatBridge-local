# 통합 평가 정합성 감사

대상은 StatBridge/StatBridge-local1과 통합 평가 120문항(QT/CQ/DA/D/E/F 각 20개)이다. 2026-10-29에 로컬 자체 텍스트 1,292개(101,466,012 bytes)를 완독 인덱싱하고 실행 경로를 추적했다. 의존성·바이너리·비밀 파일·런타임·비공개 holdout은 제외했다. Python 430개 AST 파싱 오류는 0개였다. 세부 범위와 해시는 audit/evidence/full_source_read_index.json에 있다. 제품 소스는 변경하지 않았다.

질의 120개와 수치 정답은 그대로 보존했다. E40/F34 두 건은 fixture 준비 상태를 제품 초기 상태로 가정한 잘못된 전제를 수정했다. D25/D27/D38 원본 plan.sources는 이미 A만 요구한다. A/B를 정의했더라도 실제 수식이 A만 사용하면 B는 필수 계산 입력이 아니다. 이 세 건을 데이터셋 오류로 바꾸거나 보고서 실패를 통과로 변경하지 않았다.

원본 58개 파일과 두 보고서를 보존했다. 지정된 원본 폴더에는 10월 29일 run manifest, 실제 응답 JSON, Judge 주장 분해, Playwright checkpoint, 실제 다운로드·화면 캡처가 없다. 보고서의 실행 호스트 PC-1과 현재 로컬 체크아웃도 다르다. 따라서 새 제품 E2E, 원 RAGAS 재채점, 실제 40개 다운로드 재검증은 NOT_EXECUTED다. 보고서 수치는 보고서 기반으로만 보존한다.

| 구분 | 확인 수량 | 해석 |
|---|---:|---|
| 검토한 계약 | 120 | 코드·메타데이터·기존 fixture 기준 정합성 |
| 질문 변경 / 수치 정답 변경 | 0 / 0 | 점수 상승을 위한 변경 없음 |
| 초기 상태 전제 수정 | 2 | E40, F34 |
| 로컬 컴포넌트 재현 결함 | 2종, 관련 5문항 | E26/E39/F34 표 숨김, E28/E39/F27 점 비가시성 |
| 보고서상 제품 문제 후보 | 14문항 | 원 실행 재현 확정 수량 아님; 로컬 관련 5개 포함 |
| Judge 오류 확정 | 0 | 우선 검토 5문항은 주장·판정 원본 필요 |
| 보고서상 사람 검토 대기 | 10문항, 14파일 | 실패 문항에 포함된 4파일까지 PNG/PDF 18개 전부 승인 미확인 |

분류는 PRODUCT_DEFECT, DATASET_ERROR, DATASET_AMBIGUITY, JUDGE_ERROR, EVIDENCE_GAP, HARNESS_ERROR, REVIEW_REQUIRED를 사용한다. 하나의 문항에 데이터셋 오류와 제품 결함이 동시에 있을 수 있다(F34). 증거 부족을 곧바로 제품 실패나 Judge 오류로 확정하지 않는다.

Golden Set v4.1의 개발 50/공개 테스트 70/비공개 holdout 30은 별도의 검색·발견 벤치마크다. 공개 120과 본 통합 120은 같은 집합이 아니다. 비공개 정답은 읽거나 실행 모델에 제공하지 않았다. 검색 지표를 본 E2E·계산·Faithfulness 수치와 합산하지 않는다.

## 120문항별 감사표

계산 입력/표시 계열의 빈칸은 누락이 아니라 해당 평가 범위에 역할이 없음을 뜻한다. QT의 후보 지표군은 모든 항목 동시 조회 요구가 아니다. 모든 예측 유형은 실제 관측이 없어 미관측으로 남긴다.

| ID | 범주 | 기대 유형 | 관측 유형 | 계산 입력 | 표시 전용 | 판정·근거 수준 |
|---|---|---|---|---|---|---|
| QT21-01 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-02 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-03 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-04 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-05 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-06 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-07 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-08 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: reported product issue; EVIDENCE_GAP: Judge claims unavailable |
| QT21-09 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-10 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: reported product issue; EVIDENCE_GAP: Judge claims unavailable |
| QT21-11 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-12 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-13 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-14 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-15 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-16 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-17 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-18 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-19 | QT | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| QT21-20 | QT | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-01 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-02 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-03 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-04 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-05 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-06 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-07 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-08 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-09 | CQ | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-10 | CQ | undetermined | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-11 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-12 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-13 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-14 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-15 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: reported product issue; EVIDENCE_GAP: Judge claims unavailable |
| CQ21-16 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-17 | CQ | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-18 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-19 | CQ | general | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| CQ21-20 | CQ | derived | 미관측 | 해당 없음 | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-01 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-02 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-03 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-04 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-05 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-06 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-07 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-08 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-09 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-10 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-11 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-12 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-13 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-14 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-15 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-16 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-17 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-18 | DA | general | 미관측 | 해당 없음 | requested_published_series | REVIEW_REQUIRED: execution evidence unavailable |
| DA21-19 | DA | general | 미관측 | 해당 없음 | requested_published_series | EVIDENCE_GAP: Judge claims unavailable |
| DA21-20 | DA | general | 미관측 | 해당 없음 | requested_published_series | EVIDENCE_GAP: Judge claims unavailable |
| E21 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E22 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E23 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E24 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E25 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E26 | E | not_applicable | 미관측 | 해당 없음 | a,b | PRODUCT_DEFECT: local component reproduction |
| E27 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E28 | E | not_applicable | 미관측 | 해당 없음 | a,b | PRODUCT_DEFECT: local component reproduction |
| E29 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E30 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E31 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E32 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E33 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: reported product issue |
| E34 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E35 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E36 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E37 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E38 | E | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| E39 | E | not_applicable | 미관측 | 해당 없음 | a,b | PRODUCT_DEFECT: local component reproduction |
| E40 | E | not_applicable | 미관측 | 해당 없음 | a,b | DATASET_ERROR |
| F21 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F22 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F23 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F24 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| F25 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F26 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: reported product issue |
| F27 | F | not_applicable | 미관측 | 해당 없음 | a,b | PRODUCT_DEFECT: local component reproduction |
| F28 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F29 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F30 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| F31 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| F32 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| F33 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F34 | F | not_applicable | 미관측 | 해당 없음 | a,b | DATASET_ERROR; PRODUCT_DEFECT: local component reproduction |
| F35 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F36 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F37 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: reported product issue |
| F38 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: human artifact review |
| F39 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| F40 | F | not_applicable | 미관측 | 해당 없음 | a,b | REVIEW_REQUIRED: execution evidence unavailable |
| D21 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D22 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D23 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D24 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D25 | D | derived | 미관측 | a | 해당 없음 | REVIEW_REQUIRED: reported product issue |
| D26 | D | derived | 미관측 | b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D27 | D | derived | 미관측 | a | 해당 없음 | REVIEW_REQUIRED: reported product issue |
| D28 | D | derived | 미관측 | b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D29 | D | derived | 미관측 | a | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D30 | D | derived | 미관측 | b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D31 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D32 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D33 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D34 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D35 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D36 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D37 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D38 | D | derived | 미관측 | a | 해당 없음 | REVIEW_REQUIRED: reported product issue |
| D39 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
| D40 | D | derived | 미관측 | a,b | 해당 없음 | REVIEW_REQUIRED: execution evidence unavailable |
