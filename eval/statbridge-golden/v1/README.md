# StatBridge Golden Set (lineage: statbridge-golden, v1)

정의는 `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`를 따른다.
정답의 우주는 KOSIS 한국은행 349표(`data/kosis/hankook_tables.json`)다.

## 실행
- 검증: `python3 eval/statbridge-golden/v1/scripts/validate.py`
- 채점: `python3 eval/statbridge-golden/v1/scripts/score.py <gold.jsonl> <pred.jsonl>`
- 테스트: `python3 -m pytest eval/statbridge-golden/v1/tests -q`
- 직접 확인(노트북): `notebooks/verify.ipynb` — 문제/정답 열람, validator, 채점 시연(정답·금지·오류)

## 구성
- `cases/dev.jsonl`, `cases/test.jsonl`: 정답 포함
- `cases/holdout_queries.jsonl`: 정답 미포함(공개), 정답은 비공개 저장소
- `fixtures/`: 그래프·수치 스냅샷(로컬 CSV 해시 포함)

## 검증 결과 (2026-10-06)
- 테스트: `19 passed`
- validator: `0 errors`
- scorer 자기채점(dev 2건, gold=pred): `correct=2, forbidden_hit=0, mismatch=0`

## 구현 범위 / 한계
- `interpretation` 채점은 현재 `claim_recall`, `_claim_match`가 다루는 구조화 필드의 factual consistency, `forbidden_hit`만 산출한다.
- 스펙 §3.2의 **unsupported-claim rate(환각률)** 와 **coverage** 는 자유 텍스트 claim 추출이 필요해 **보류(deferred)** 한다.
- 그래프 채점은 정답 계열 ID를 직접 지정하는 모드만 있고, 자연어 질의 → 계열 선택까지 보는 `graph_e2e` 모드는 아직 채점하지 않는다.
- 따라서 `exact`를 아직 완전한 factual consistency로 읽으면 안 된다.
