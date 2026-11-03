# RAGAS 증거와 적용성 감사

원 점수는 수정하지 않았다. 아래는 보고서가 제시한 값이며 원시 JSON으로 재계산한 값이 아니다. RAGAS 0.4.3 collections Faithfulness, Judge gpt-6.1-sol. live 58개 채점 평균 0.943350, 22개 N/A. QT 11개 평균 0.818182/NA9, CQ 10개 0.971429/NA10, DA 20개 0.95/NA0, D 17개 1.0/NA3. replay DA20개 0.95, D18개 1.0/NA2. live/replay는 합산하지 않는다.

분류 함수 QT 20/20과 API 경로 19개 일치+1개 미관측은 별개다. Faithfulness는 retrieval context가 응답 주장을 뒷받침하는지를 평가하며 query type 정답률이나 데이터 계산 정확도와 대체 관계가 아니다. CQ의 확인 필요 결정이 맞더라도 질문 대상·기존 조건 보존은 별도 의미 검토가 필요하다.

| 우선 검토 ID | 보고서의 주장 | 이번 판정 | 필요한 직접 증거 |
|---|---|---|---|
| QT21-08 | 0점; 대출·판매신용을 가계신용으로만 요약 | PRODUCT_DEFECT/JUDGE_ERROR 미확정 | 실제 응답, 원 지표 context, 주장 분해와 supported 판정 |
| QT21-10 | 0점; 부산+대구 합계를 부산으로만 요약 | PRODUCT_DEFECT/JUDGE_ERROR 미확정 | 지역별 원자료, 합계 실행 결과, 요약 주장 |
| CQ21-15 | 0.714286; 원계열/순환변동치 명칭 혼동 | 의미 검토 필요 | 실제 확인 질문/응답, 명칭 메타데이터, 주장 분해 |
| DA21-19 | live 0점; SNA2008 context 누락 가능 | EVIDENCE_GAP | 당시 DT_284Y001 메타데이터 경로·입력 context |
| DA21-20 | replay 0점; 질문에서 SNA 기준 보충 가능 | EVIDENCE_GAP/Judge 검토 | 당시 DT_284Y002 context, 질문 제외 후 주장 판정 |

현재 로컬 메타데이터의 자금순환표 경로에는 2008 SNA 기준·상세자금순환표(2018~)가 존재한다. 이는 현재 카탈로그 사실이며 과거 Judge가 이를 받았다는 증거가 아니다. 응답이 맞고 context가 빠졌다면 EVIDENCE_GAP, context가 충분한데 unsupported라면 JUDGE_ERROR 후보, context와 응답이 실제 충돌하면 PRODUCT_DEFECT 후보로 분리한다. 이번 Judge 오류 확정은 0개다.

원본 22개 NA의 경우별 응답·이유 JSON은 없다. audit/ragas_applicability.json은 보고서 수량을 22개 슬롯으로 보존하고 식별되지 않은 case_id는 null로 둔다. QT21-11 및 D25/D27/D38만 보고서 기반 연결이며 나머지 ID를 추정하지 않는다. 확인 질문 자체 무주장, 메타데이터 확인 중, 제공자 실패, 계산 미완료, Judge 오류는 서로 다른 적용 제외 사유다. NA를 0점이나 1점으로 환산하지 않는다.

scripts/export_reviewed_ragas.py는 같은 run_id/case_id의 실제 response 캡처와 API·검색·메타데이터·실제 계산 증거만 받는다. 파일 SHA-256과 payload selector를 검증하며 질문/정답/생성 설명을 context로 넣지 않는다. scripts/reviewed_evidence.py가 출처·실행 결합을 검증한다. 새 입력·Judge 버전·원 점수·재채점 점수는 별도로 보존해야 한다.

재채점 상태: NOT_EXECUTED. 변경 전 점수는 audit/ragas_regrade.json에 보고서 값으로 보존했고 변경 후 점수·차이는 null이다. 원 JSON·캡처가 없으므로 실제 주장별 supported/unsupported 판정을 생성하지 않았다. AI가 사람 시각 승인도 대신하지 않는다.
