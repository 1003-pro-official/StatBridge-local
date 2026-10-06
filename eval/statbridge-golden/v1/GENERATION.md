# 생성 절차 (SOP)

정의: `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`

1. 씨앗 선정: `research/그림표-분석/그림표_마스터.csv`에서 5개 발간물에 고르게, `사용 데이터·출처`가 `한국은행` 포함인 행 우선.
2. 문장 생성(LLM 보조): 유형별 문장 후보 생성(공식/일상/조건/복수/모호/범위 밖/후속).
3. 정답 부여: 표 ID는 `data/kosis/hankook_tables.json`(349표)에서 매핑. 수치·그래프는 `data/tables/`의 로컬 CSV에서 fixture 생성(source_file_sha256 기록).
4. 오답 함정: `forbidden_table_ids`(sibling 오답), `forbidden_claims`(방향 반전·환각·전망 단정).
5. 사람 검수: 원문·카탈로그 대조 후 `review.human_approved=true`.
6. 누수: holdout은 `cases/holdout_queries.jsonl`에 `id/query/prior_turns`만. 정답은 비공개 저장소.
7. 검증·채점: `validate.py` 0 errors, `score.py`로 오답 분류 확인.

분할 목표는 `manifest.json` 참조(총 90: dev 30 / test 42 / holdout 18).
