# 정성 검수 안내

ai-assisted 초안. 실제 점수는 검수자가 응답을 보고 기록합니다. 작성자는 자기 사례를 승인하지 않습니다.

## 대상

정성 검수가 **필수**인 모드: `report` 12, `follow_up` 8, `edit` 8.
`query_output`·`derived`는 선택이며 `facts`만 보아도 됩니다.

## 항목과 0/1/2 기준

| 항목 | 2점 | 1점 | 0점 |
|---|---|---|---|
| facts | 수치·시점·방향·해석이 근거와 일치 | 사실은 맞고 표현이 모호 | 수치·해석 오류 또는 근거 없는 주장 |
| completeness | 핵심 요구·제약을 모두 설명 | 부가 설명 일부 부족 | 핵심 요구 누락·다른 답변 |
| clarity | 단위·기준·용어가 명확 | 장황·일부 불명확 | 이해를 막거나 오도 |
| source_limits | 출처·자료 버전·산식·한계 확인 가능 | 근거를 찾기 어려움 | 허위 출처·한계 은폐 |
| visual | 읽기 쉽고 비교 목적·편집 요구 충족 | 가독성 일부 개선 필요 | 축·범례·종류가 의미 왜곡 |
| conversation_recovery | 맥락 유지·필요한 확인·복구 안내 | 불필요한 왕복·안내 부족 | 맥락 상실·잘못된 유도·복구 불가 |

## 규칙

1. 적용하지 않는 항목만 `not_applicable`에 넣고 점수는 `null`로 둡니다. `facts`는 N/A로 뺄 수 없습니다.
2. 미검수(`null`)는 0점이 아닙니다. 검수하지 않았으면 `human_approved`를 켜지 않습니다.
3. `evidence_notes`에 점수의 근거가 된 응답 문장이나 화면 위치를 적습니다. 빈 문자열은 무효입니다.
4. 치명 오류 의심과 0점은 표본 밖이어도 두 번째 검수자가 확인합니다. 불일치는 평균으로 덮지 않고 보류합니다.
5. `input_sha256`·`expected_sha256`·`prediction_sha256`이 바뀌면 이전 검수는 효력이 없습니다.
6. 잘못된 응답도 검수 완료일 수 있습니다. 검수 완료와 통과는 다릅니다.

## 절차

```bash
# 1) 실행 후 빈 검수 파일 생성 (기존 파일은 덮어쓰지 않음)
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/review_packet.py \
  .venv/cache/statbridge-e2e-v1/predictions-02.jsonl \
  --output .venv/cache/statbridge-e2e-v1/review-02.jsonl

# 2) 검수자가 scores/notes/reviewer 를 채운 뒤 채점
.venv_runtime/bin/python eval/statbridge-e2e/v1/scripts/score.py \
  .venv/cache/statbridge-e2e-v1/predictions-02.jsonl \
  --reviews .venv/cache/statbridge-e2e-v1/review-02.jsonl \
  --output .venv/cache/statbridge-e2e-v1/score-02-reviewed.json
```

## 보고

정량 통과율과 정성 평균을 **합산하지 않고** 나란히 보고합니다. 최소한 다음을 적습니다.

- 모드별 분모(전체/실행/검수)
- 정량: 통과·실패·미관측·미실행·제외
- 정성: 항목별 n과 평균, 치명 오류 건수
- 미검수 건수와 사유
