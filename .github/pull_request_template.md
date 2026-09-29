## 무엇을 바꾸나요
<!-- 변경 목적과 범위를 1~3줄로 적습니다. -->

## 관련 이슈
<!-- 예: Closes #12. 없으면 "없음". -->

## 평가 계열 (해당 시)
<!-- 없음 / 표 탐색(table-discovery) / 전체 흐름(end-to-end). 두 계열은 버전과 점수를 혼용하거나 비교하지 않습니다. -->

## 검증
아래를 실행했고 결과를 붙입니다. 실행하지 못한 항목은 이유를 적습니다.

- [ ] `PYTHONPATH=src/backend:src/agent .venv/bin/python -m pytest -q tests eval/table-discovery/v4.1/tests`
- [ ] `.venv/bin/python eval/table-discovery/v4.1/scripts/validate_v41.py`
- [ ] `cd src/agent/frontend && pnpm build`
- [ ] 외부 KOSIS·NCP 호출 / 347 CSV 조회 (해당 시, 키와 데이터가 있는 환경)

```text
<!-- 명령 출력 또는 요약 -->
```

## 공개·비공개 경계
- [ ] 비공개 저장소 자료와 holdout 정답을 포함하지 않았습니다.
- [ ] `.env`, API 키, 원자료 CSV, 벡터 DB, 생성된 평가 결과를 포함하지 않았습니다.

## 에이전트 사용
- [ ] LLM·에이전트로 만든 변경이며(`ai-assisted`), 사람이 diff 전체를 확인했습니다.

## 리뷰어에게
<!-- 리스크, 한계, 확인이 필요한 부분 -->
