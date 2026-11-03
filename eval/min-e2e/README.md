# 최소 E2E 평가 계열 (v1 ~ v2.2)

2026-11-03 정리 · ai-assisted · 공개 개발 평가 · 사람의 최종 승인 아님

이 디렉터리는 2026-10-23~11-02에 실행한 최소 E2E 평가의 **질문·정답·기준·서술 보고서**를 보관한다. 실행 당시의 예측·점수·관측·화면 캡처는 넣지 않는다(`evaluation_runs/`는 Git 제외). 각 버전의 해석과 한계는 [최소 E2E 평가 이력](../../docs/evaluation/min-e2e-history/README.md)과 아래 문서를 따른다.

## 버전

| 버전 | 문항 | 실행일 | 이 디렉터리에 있는 것 | 해석 문서 |
|---|---:|---|---|---|
| [v1.4](v1.4/) | 50 | 2026-10-27 | 질문·정답·rubric·관측·승인 기록·manifest·수집/렌더 스크립트 | [v1.4](../../docs/evaluation/min-e2e-history/v1.4.md) |
| [v1.4 정성 3인](v1.4/qualitative-10-3p/) | 10 (v1.4 부분집합) | 설계 2026-10-28, 종합 보고서 2026-11-03 | 설계·기준·기록지 양식·종합 보고서 | [정성평가 3인](../../docs/evaluation/2026-11-03-qualitative-10-3p.md) |
| [v2](v2/) | 60 (D·E·F 각 20) | 2026-10-27 | 데이터셋·단계 기대·fixture·운영 명세·검증 결과 | [v2](../../docs/evaluation/min-e2e-history/v2.md) |
| [v2.1](v2.1/) | 60 (QT·CQ·DA 각 20) | 2026-10-27 | 질문·환경·해시·정책·실행/채점 스크립트 | [v2.1](../../docs/evaluation/min-e2e-history/v2.1.md) |
| [v2.2](v2.2/) | 120 (v2 + v2.1) | 2026-10-30 | runner·oracle·fixture·스크립트·검토 문서·정책 | [v2.2](../../docs/evaluation/2026-11-03-v22-evaluation-set.md) |
| [v2.2 RAGAS 80](v2.2/ragas-20261102/) | 80 (E·F 제외) | 2026-11-02 | 실행·패치 검증 보고서 3건 | [RAGAS·Judge](../../docs/evaluation/2026-11-02-ragas-llm-judge.md) |
| [judge-v3](judge-v3/) | 10 (v1.4 부분집합) | 2026-11-02 | Judge 기준·프롬프트·결과 스키마·실행 연결 양식 | [RAGAS·Judge](../../docs/evaluation/2026-11-02-ragas-llm-judge.md) |

## 읽는 순서

1. 버전 문서에서 평가 목적·입력·결과·한계를 확인한다.
2. 이 디렉터리에서 질문과 정답을 확인한다.
3. 점수를 재현하려면 실행 시점의 제품 커밋·모델·원자료가 필요하다. 현재 `main`에서 새로 얻은 값으로 과거 점수를 대체하지 않는다.

## 포함하지 않은 것

원시 예측·점수 JSON, API 원응답, 원자료 CSV, 화면·다운로드 캡처, 내장 evidence ZIP, `.env`·키, 인증 DB. 원본 묶음은 저장소 밖 로컬 아카이브(`~/statbridge-eval-archive/2026-11-03/`)에 두었고 `sha256.txt`로 식별한다.

## 공개 범위

정답이 포함된 공개 개발용 평가셋이다. **블라인드 평가에 사용할 수 없다.** 정답을 본 사람·모델이 참여한 실행은 독립 평가로 표시하지 않는다. 비공개 holdout 정답과 평가기는 `StatBridge-evaluation-private`에만 둔다.
