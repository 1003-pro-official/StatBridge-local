# 인계: C 단계(유료 모델 실행) 결정서

담당자: **kimmin** · 2026-10-21 · ai-assisted

이 문서는 C 단계의 **선택지만** 담당자가 정하도록 만든 것입니다. A·B 단계는 이미 실행되어 결과가 있습니다. C는 담당자가 승인하기 전까지 **절대 실행되지 않습니다.**

## 지금 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| A | 계약·검증·provider 확장 | 완료 |
| B | `query_output`·`edit`·`follow_up` 오프라인 실행 | 완료 (결과는 VALIDATION.md) |
| C | `derived`·`report` 유료 모델 실행 | **대기 — 담당자 결정 필요** |

## C가 필요한 이유

`derived`(파생지표 8건)와 `report`(보고서 12건)는 제품 안에서 **LLM이 계획·문장을 만드는 단계**가 있습니다. 고정 데이터로는 대체할 수 없어서, 유료 모델 호출 없이는 채점할 수 없습니다.

## 결정 1. 프로필

`profiles.json`의 `profiles` 두 가지 중 하나를 고르고 `selected_profile`에 이름을 적습니다.

| 선택 | 의미 | 장점 | 단점 |
|---|---|---|---|
| `single_model` | 한 모델이 계획과 문장 모두 | 설정·비용 단순 | 역할별 품질 차이를 못 봄 |
| `split_models` | 계획용/문장용 분리 | 역할별 비교 가능 | 모델·키 2개 관리 |

두 경우 모두 `models`의 `main_model`·`text_model`·`edit_model` **빈칸을 담당자가 채워야** 합니다. 저장소에는 기본 모델 ID를 넣지 않았습니다.

## 결정 2. 반복 횟수

| 값 | 의미 | 비용 |
|---|---|---|
| `1` | 1회 실행 | 기준 |
| `3` | 3회 반복 | 약 3배 |

3회를 고르면 사례별 과반 성공 규칙을 쓸 수 있습니다. 1회면 단일 실행 결과입니다.

## 결정 3. 비용 상한

`approval.cost_cap_usd`에 **숫자**를 넣습니다. 상한이 없으면 실행기가 거부합니다. 실행 후 실제 비용은 응답에서 관측된 값만 기록하며, 관측되지 않으면 `null`로 남깁니다.

## 결정 4. 실행 범위

`approval.modes`에 실행할 모드를 적습니다.

| 선택 | 문항 |
|---|---|
| `["derived"]` | 8 |
| `["report"]` | 12 |
| `["derived", "report"]` | 20 |

## 결정 5. 승인 기록

`approval.approved_by`에 이름, `approved_at`에 ISO 날짜(`2026-10-22`)를 적습니다. 이 두 칸이 비면 실행기가 거부합니다.

## 채우는 예시

```json
{
  "selected_profile": "single_model",
  "approval": {
    "approved_by": "kimmin",
    "approved_at": "2026-10-22",
    "cost_cap_usd": 20,
    "repeats": 1,
    "modes": ["derived", "report"]
  },
  "profiles": {
    "single_model": {
      "models": {"main_model": "<모델ID>", "text_model": "<모델ID>", "edit_model": "<모델ID>"}
    }
  }
}
```

## 실행

```bash
# 1) 먼저 승인 없이 계획만 확인 (실행 안 됨)
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/run_model.py \
  --profile single_model --mode derived --mode report --repeats 1

# 2) 승인 후 실행 (제품 서버가 떠 있어야 함)
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/run_model.py \
  --profile single_model --mode derived --mode report --repeats 1 \
  --base-url http://127.0.0.1:8000 --allow-paid \
  --output .venv/cache/statbridge-e2e-v1/model-runs/run-01.jsonl

# 3) 채점 (정량)
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/score.py \
  .venv/cache/statbridge-e2e-v1/model-runs/run-01.jsonl \
  --output .venv/cache/statbridge-e2e-v1/model-runs/score-01.json

# 4) 정성 검수 파일 생성 후 REVIEW.md 기준으로 채점
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/review_packet.py \
  .venv/cache/statbridge-e2e-v1/model-runs/run-01.jsonl \
  --output .venv/cache/statbridge-e2e-v1/model-runs/review-01.jsonl
```

## 실행기가 거부하는 조건

아래 중 하나라도 해당하면 실행되지 않습니다. 일부러 그렇게 만들었습니다.

- `--allow-paid` 없음
- `selected_profile`이 비어 있음
- `approved_by`·`approved_at`이 비어 있음
- `cost_cap_usd`가 숫자가 아님
- `approval.repeats`와 `--repeats`가 다름
- `approval.modes`와 `--mode`가 다름
- `models`에 빈칸이 있음
- 필요한 API 키 환경변수가 없음
- `--base-url`이 없음

## 반드시 지킬 것

1. **정답을 고치지 않습니다.** 실행 결과가 나쁘다고 `expected`·오라클·질의를 바꾸면 그 실행은 폐기 대상입니다.
2. **모델 귀속은 미확인입니다.** API가 응답 모델을 노출하지 않아 `actual_models`는 `null`, `model_attribution`은 `unverified`로 기록됩니다. "GPT-5.4로 측정했다"고 쓰려면 별도 근거가 필요합니다.
3. **숫자 값·예측·검수 결과는 커밋하지 않습니다.** `.venv/cache/statbridge-e2e-v1/`에만 둡니다.
4. **정성 검수 없이 `passed`가 되지 않습니다.** 정량 통과는 `pending_review`로 남습니다.
5. **비공개 holdout은 이 실행에 넣지 않습니다.** 질의 40건은 별도 평가 때 사용합니다.

## 결과를 보고할 때

- 모드별 분모: 전체 / 실행 / 채점 가능 / 검수 완료
- 정량과 정성을 합산하지 않음
- 유료 호출 횟수와 실제 관측 비용(있으면)
- `unverified` 모델 귀속을 명시
- 실패 원인을 제품·질의·하네스로 구분

## C 이후 남는 일

1. Tier A 오라클 26건 사람 검산 (`oracle_review.py`가 만든 표 사용)
2. `report` 응답 정성 검수 (검수자 2명)
3. `derived` 계산 결과의 독립 재검산
4. 비공개 holdout 40건 실행 (정답은 저장소 밖)
5. 결과를 `VALIDATION.md`·`manifest.json`에 반영
