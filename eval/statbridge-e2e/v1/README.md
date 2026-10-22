# StatBridge E2E 업무 흐름 평가 v1

ai-assisted · 사람 검수 전 · 공식 성능 아님. `eval/bok-reproduction/v1`·`v2`, `eval/end-to-end/v1`·`v2`, `eval/table-discovery/*`와 **점수를 합치지 않습니다.**

## 무엇을 평가하나

한국은행 자료 담당자의 실제 요청을 제품의 **실제 API 경로**로 실행해, 질의 → 표·계열 선택 → 기간 확정 → 출력까지 확인합니다. 파생지표·보고서·후속 대화·편집은 사례 계약만 두고, 모델 어댑터가 없으면 `not_executed`로 남깁니다.

- 공개 120문항 (dev 48 / test 72), 비공개 holdout 질의 40건
- 공식 채점 단위는 **36개 유형 그룹**입니다. 변형은 모드별 진단으로만 봅니다
- 정답 계층: 공개 계약(표·항목·분류·주기·기간) / 비공개 숫자 오라클 / 비공개 holdout 정답

## 근거

`research/kosis-bok-reproduction`의 36개 유형(`재현매핑.csv`), 재현명세 3건(`원본재현명세.json`), 업무형 질의(`질의집.jsonl`)에서 생성했습니다. 연구 폴더의 `실행판정`(제품이 출력했다는 기록)은 정답으로 쓰지 않았습니다.

| Tier | 유형 | 숫자 채점 |
|---|---:|---|
| A | 8 (ESI 2, RATE 4, CREDIT 2) | 가능 — `data/tables` CSV에서 독립 추출 |
| B | 25 | 불가 — 계열·기간만 |
| C | 3 (IIP-02, IIP-03, LOAN-01) | 채점 제외 |

## 파일

| 파일 | 내용 |
|---|---|
| `inventory.json` | 36유형 조인, Tier·기간 범위, research 파일 해시 |
| `schema.json` | 사례 구조 |
| `cases/dev.jsonl`, `cases/test.jsonl` | 정답 계약 포함 |
| `cases/holdout_queries.jsonl` | 질의만 |
| `scripts/build_inventory.py` | research → inventory |
| `scripts/build_cases.py` | 사례 생성 + `.venv/cache/statbridge-e2e-v1/{oracles,provider}.json` |
| `scripts/validate.py` | 누출·기간·ID·오라클 해시 검사 |
| `scripts/run.py` | 고정 provider로 실제 앱 실행 (query_output) |
| `scripts/score.py` | 정량 채점 + 정성 게이트 |
| `scripts/review_packet.py` | 빈 사람 검수 양식 |
| `scripts/oracle_review.py` | Tier A 숫자 검산표 (비공개) |
| `scripts/offline_app.py` | edit·후속 실행용 오프라인 앱 경계 |
| `scripts/run_model.py` | C단계 유료 실행 (승인 전 거부) |
| `profiles.json` | C단계 모델·반복·상한 선택지 |
| `REVIEW.md` | 정성 0/1/2 rubric |
| `HANDOFF.md` | **담당자 결정서** |
| `scripts/manifest.py` | 파일·제품 리비전 해시 |

## 실행

```bash
python3 eval/statbridge-e2e/v1/scripts/build_inventory.py
python3 eval/statbridge-e2e/v1/scripts/build_cases.py
python3 eval/statbridge-e2e/v1/scripts/validate.py
python3 -m pytest -q eval/statbridge-e2e/v1/tests
```

오프라인 실행은 앱 의존성이 설치된 인터프리터가 필요합니다. `query_output`·`edit`·`follow_up`이 실행되고, `derived`·`report`는 C단계(유료) 승인 전까지 `not_executed`입니다.

```bash
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/run.py --output .venv/cache/statbridge-e2e-v1/predictions-01.jsonl
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/score.py .venv/cache/statbridge-e2e-v1/predictions-01.jsonl --output .venv/cache/statbridge-e2e-v1/score-01.json
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/review_packet.py .venv/cache/statbridge-e2e-v1/predictions-01.jsonl --output .venv/cache/statbridge-e2e-v1/review-01.jsonl
```

## 읽을 때 주의

- 정량 통과만으로 성공이 아닙니다. 정성 검수가 없으면 `pending_review`입니다.
- Tier B는 숫자를 채점하지 않으므로 120문항 전체를 "정확도"로 표기하면 안 됩니다.
- Tier C는 정답이 아니라 미해결 탐침입니다.
- 모델·실시간 KOSIS 호출은 하지 않습니다.
- 숫자 값·예측·검수 결과는 `.venv/cache/statbridge-e2e-v1/`에만 둡니다.

현재 실행 결과와 한계는 [VALIDATION.md](VALIDATION.md), 설계는 [DESIGN.md](DESIGN.md), 인계 결정은 [HANDOFF.md](HANDOFF.md)를 보세요.
