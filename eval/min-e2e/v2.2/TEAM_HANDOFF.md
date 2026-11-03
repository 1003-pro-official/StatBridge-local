# StatBridge v2.2 평가·패치 전달본

이 버전을 새 평가의 기준으로 사용하세요. 최종 사람 승인 의무는 삭제되었습니다. 규칙과 근거가 충족되면 PASS, 불일치면 FAIL, 증거가 없으면 EVIDENCE_GAP입니다. 기존 실제 파일 사람 판정은 보존했고 CQ는 AI 직접 근거 검토로 대체했습니다. 파일 시각검토의 실제 수행자와 자동 검증, 새 제품 실행 여부는 계속 구분합니다.

1. runner/ 질문·시나리오만 프로그램에 입력합니다. oracle/ 정답은 비교용이며 모델 검색문서·프롬프트·RAGAS factual context에 넣지 않습니다.
2. 대상 제품 커밋·모델·환경·시각·원자료를 고정하고 새 run_id를 사용합니다. CQ16의 최신월은 호출 전에 선택 원계열의 공식 참조로 동결합니다.
3. CQ는 확인 여부뿐 아니라 질문+선택지의 대상, 확정 조건 보존, 확인 전 실제 실행 trace를 평가합니다. 일반 안내문만으로 의미 판정하거나 bool(output)로 실행 여부를 대신하지 않습니다.
4. D는 원자료·계산 의존성·단위·수치와 요약 지표 의미를 나눠 봅니다. D23은 계산 통과/요약 실패입니다. 이번 summary_semantics는 기존 D 수치 검사의 점수 변화와 따로 비교합니다.
5. F27은 관측점 편집 기능이 있으므로, 저장된 색상만으로 통과시키지 않습니다. B의 2025년 6월 #E53935 점이 화면과 PNG/SVG에 실제 표시돼야 합니다. F22는 화면의 범례 읽기 순서를 PDF에서도 보존해야 합니다.
6. 실패 원인을 확인한 뒤 제품을 패치하고 새 실행으로 재평가합니다. 원본 실행·Judge 점수·검토 판정은 덮어쓰지 않습니다. 정답 오류는 독립 근거와 변경 이력을 기록하여 별도 버전으로 수정합니다. 최종 사람 승인 절차를 다시 추가하지 않습니다.

## 파일

- REPORT.md: 최신 범위·점수·정정 내용.
- CQ_SEMANTIC_REVIEW.md: 20문항별 직접 판정과 이유.
- D23_ADJUDICATION.md: 원문·독립 수치·주장별 판정 요약.
- evaluation_policy.json: 승인 의무 제거 정책.
- results/ai_adjudication_20261030/: 원시 파일 해시가 연결된 검토, 관측값, 최종 점수, 419개 회귀 검사.
- oracle/cases.jsonl: 질문·expected 정답은 직전 버전과 동일. 최종 승인 필드는 이력으로 보존하고 활성 기준에서 제외.
- evidence/의 실제평가 ZIP: 기존 120문항 응답·화면·다운로드·RAGAS 원시 판정. 새 결과를 과거 실제 실행에 덮어쓰지 않습니다.
- docs/history_pre_v22/와 기존 baseline_reference/audit/results/live_human_20261030/: 과거 시점 자료이며 현재 승인 정책과 점수보다 우선하지 않습니다.

## 재현 명령

증거 ZIP을 evidence/에 풀면 evidence/StatBridge_live_verification/ 아래에 runs가 생깁니다. 제품 의존성이 설치된 Python을 사용합니다.

```powershell
python -B scripts/score_live_bundle.py --evidence-root evidence/StatBridge_live_verification --output results/replay_new.json
python -B scripts/validate_v22.py --evidence-root evidence/StatBridge_live_verification --output results/validation_new.json
```

기존 validate_reviewed.py는 이전 승인 정책용 역사적 테스트입니다. 현재 기준은 validate_v22.py입니다. 419개 회귀 검사와 이전 1,015개 검사를 제품 성공률로 합산하지 않습니다. 이번에는 기존 증거를 재채점했으며 제품 코드·실행 결과·RAGAS API를 새로 생성하지 않았습니다.
