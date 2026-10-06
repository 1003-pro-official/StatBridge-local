# StatBridge Golden Set (lineage: statbridge-golden, v1)

정의는 `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`를 따른다.
정답의 우주는 KOSIS 한국은행 349표(`data/kosis/hankook_tables.json`)다.

## 실행
- 검증: `python3 eval/statbridge-golden/v1/scripts/validate.py`
- 채점: `python3 eval/statbridge-golden/v1/scripts/score.py <gold.jsonl> <pred.jsonl>`
- 테스트: `python3 -m pytest eval/statbridge-golden/v1/tests -q`

## 구성
- `cases/dev.jsonl`, `cases/test.jsonl`: 정답 포함
- `cases/holdout_queries.jsonl`: 정답 미포함(공개), 정답은 비공개 저장소
- `fixtures/`: 그래프·수치 스냅샷(로컬 CSV 해시 포함)

## 검증 결과 (2026-10-06)
- 테스트: `17 passed`
- validator: `0 errors`
- scorer 자기채점(dev 2건, gold=pred): `correct=2, forbidden_hit=0, mismatch=0`
