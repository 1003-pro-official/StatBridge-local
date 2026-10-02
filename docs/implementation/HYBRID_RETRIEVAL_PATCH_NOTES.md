# StatBridge 하이브리드 검색 패치

검색 경로는 `HCX-003 구조화 -> Embedding v2 후보 생성 -> Chroma Top-K -> NCP Reranker -> 사전 규칙 점수 -> 확신도/역질문 -> MCP/KOSIS`입니다.

- Embedding과 Reranker는 후보 순서만 바꾸며 API ID를 만들지 않습니다.
- `table_id`, `itmId`, `objL1..8`은 항상 `stat_language_dictionary.json`에서 재검증합니다.
- Chroma가 없거나 API 호출이 실패하면 기존 규칙 검색으로 자동 복구됩니다.
- `data/vector_documents`에는 재임베딩 가능한 문서와 캐시가, `data/vector_store`에는 영구 인덱스가 저장됩니다.
- `scripts/windows/RUN_VECTOR_BUILD.cmd`로 전체 인덱스를 재구축하고 `scripts/windows/RUN_RETRIEVAL_EVAL.cmd`로 A/B/C 결과를 생성합니다.
- 후보 디버그 필드: `vector_score`, `rerank_score`, `rule_score`, `confirmed_bonus`, `negative_penalty`, `final_score`.

환경변수는 `.env.example`의 `STATBRIDGE_*`, `NCP_EMBEDDING_URL`, `NCP_RERANKER_URL`을 참고하십시오.
