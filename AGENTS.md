# StatBridge-local 작업 규칙

이 파일은 이 저장소 전체에 적용됩니다. 사람과 자동화 도구는 변경 전에 저장소의 `README.md`와 해당 영역의 코드를 확인합니다.

## 저장소의 역할

- 이 저장소는 Backend·MCP·Agent·프런트엔드와 공개 평가 자료를 관리합니다.
- 화면의 API는 `src/agent/bridge_api.py`의 `/api/query`, `/api/catalog`, `/api/health`입니다. 새 화면 기능은 UI → Agent → MCP → KOSIS 또는 로컬 CSV 흐름을 따릅니다.
- `data/processed/`의 메타데이터는 추적합니다. `data/tables/`의 원자료 CSV 347개는 외부에서 공급하며 Git에 넣지 않습니다.

## 공개·비공개 경계

- 비공개 `StatBridge-evaluation-private` 저장소와 `holdout_answers.jsonl`은 이 저장소의 작업, 검색, 인덱싱, 테스트 입력, 프롬프트에 사용하지 않습니다. 같은 로컬 작업공간에 보이더라도 열거나 복사하지 않습니다.
- 개발 중 평가는 `eval/golden-set-v4.1/dev.jsonl`과 `test.jsonl`로 수행합니다. 공개 `holdout_queries.jsonl`에는 정답을 붙이거나 개발 피드백을 기록하지 않습니다.
- `.env`, API 키, 원자료 CSV, 벡터 DB, 예측·평가 결과, 임시 파일은 커밋하지 않습니다. 샘플 설정은 실제 값이 없는 `.env.example`에만 둡니다.
- 비공개 자료가 diff나 PR에 섞인 것을 발견하면 게시를 멈추고 PM에게 알립니다. `.gitignore`만으로 유출을 막을 수 있다고 가정하지 않습니다.

## 변경과 검증

1. 기능 브랜치에서 변경하고 PR로 `main`에 반영합니다. `main`에 직접 푸시하거나 강제 푸시하지 않습니다.
2. 기존 API 계약이나 데이터 선택 방식을 바꾸면 README와 관련 테스트를 함께 갱신합니다. 실제 관측값이 없으면 생성하거나 성공으로 표시하지 않습니다.
3. PR 전에 변경 파일 목록과 diff를 확인하고, 최소한 다음 검증을 실행합니다. 실행할 수 없는 검증과 이유는 PR에 기록합니다.

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python -m pytest -q tests eval/golden-set-v4.1/tests
.venv/bin/python eval/golden-set-v4.1/scripts/validate_v41.py
cd src/agent/frontend && pnpm build
```

외부 KOSIS·NCP 호출과 347개 CSV를 이용한 조회는 키와 데이터가 제공된 환경에서 별도로 확인합니다. PR에는 확인한 범위와 남은 제한을 명시합니다.
