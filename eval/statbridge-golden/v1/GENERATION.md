# 생성 절차 (SOP)

정의: `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`

1. 씨앗 선정(table-first): `data/kosis/hankook_tables.json`(349표)에서 표를 고른다. 표 자체가 정답이므로 정확·검증 가능하다. 5개 발간물 주제에 골고루 대응하도록 고르고, `research/그림표-분석/그림표_마스터.csv`는 출처·분석목적·문장 표현 참고용으로만 본다(그림 제목→표 자동 매핑은 신뢰 수율이 낮아 쓰지 않는다). `external_only`(외부 단독) 소재는 현실적인 질문만 골라 `no_match` 부정 케이스로 쓴다.
2. 문장 생성(LLM 보조): 고른 표에 대해 유형별 문장 후보 생성(공식/일상/조건/복수/모호/범위 밖/후속).
3. 정답 부여: 표 ID는 이미 고른 카탈로그 표. 수치·그래프는 그 표의 `data/tables/` 로컬 CSV에서 fixture 생성(source_file_sha256 기록).
4. 오답 함정: `forbidden_table_ids`(sibling 오답), `forbidden_claims`(방향 반전·환각·전망 단정).
5. 사람 검수: 원문·카탈로그 대조 후 `review.human_approved=true`.
6. 누수: holdout은 `cases/holdout_queries.jsonl`에 `id/query/prior_turns`만. 정답은 비공개 저장소.
7. 검증·채점: `validate.py` 0 errors, `score.py`로 오답 분류 확인.

분할 목표는 `manifest.json` 참조(총 90: dev 30 / test 42 / holdout 18).
