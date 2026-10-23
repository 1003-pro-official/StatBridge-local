# 한국은행 평가 기간 범위 확장 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** BOK v1 평가에 고정 스냅샷으로 검증 가능한 장기 월간·분기·연간 질의 4건을 더한다.

**Architecture:** 기존 12개 canonical 계약과 6개 짧은 기간 probe는 유지한다. build.py의 기간 변형 명세에 연속 관측 길이 검증을 추가하고, dataset v1.2의 pilot 22건 및 오라클 해시를 재생성한다. 새 cases는 query-only이며 숫자 답은 기존 로컬 cache에만 둔다.

**Tech Stack:** Python 3, JSONL, existing FrozenProvider/oracle builder, pytest.

---

### Task 1: 장기 기간 probe 회귀 테스트

**Files:**
- Modify: `eval/bok-reproduction/v1/tests/test_evaluation.py`

**Step 1: 실패 테스트 작성**

- 기대하는 네 기간: 36개월 PPI, 24개월 수출물가, 8분기 가계신용, 5년 연간 PPI.
- 각 probe의 질의가 기간 전체를 나타내고, `input.actions`가 없으며 oracle의 점 개수가 36/24/8/5인지 검사한다.
- canonical 12개의 expected는 그대로인지 검사한다.

**Step 2: 실패 확인**

Run: `/tmp/statbridge-bok-venv/bin/python -m pytest -q -p no:cacheprovider eval/bok-reproduction/v1/tests -k long_period`

Expected: 새 probe가 없어 실패.

### Task 2: 생성기와 데이터 버전 개정

**Files:**
- Modify: `eval/bok-reproduction/v1/scripts/build.py`
- Modify: `eval/bok-reproduction/v1/scripts/evaluate.py`
- Regenerate: `eval/bok-reproduction/v1/pilot.jsonl`
- Regenerate: `eval/bok-reproduction/v1/gold-review-template.jsonl`
- Local only: `.venv/cache/kosis-bok-reproduction/evaluation-v1/oracles.json`

**Steps:**

1. 기간 명세에 월간 2023-09~2026-08, 월간 2024-10~2026-09, 분기 2024Q3~2026Q2, 연간 2021~2025를 추가한다.
2. 연간 PPI는 월간 원본과 같은 총지수 분류의 연간 원천 계열을 사용한다.
3. 기대 기간의 모든 월/분기/연도가 고정 제공자에 존재하지 않으면 생성 오류를 낸다.
4. manifest version 1.2, pilot 22건(12 canonical+10 period probes)으로 검증 조건을 갱신한다.

### Task 3: 문서·manifest·검증

**Files:**
- Modify: `eval/bok-reproduction/v1/README.md`
- Modify: `eval/bok-reproduction/v1/VALIDATION.md`
- Modify: `eval/bok-reproduction/v1/manifest.json`
- PR: #45, DRAFT 유지

Run:

```bash
/tmp/statbridge-bok-venv/bin/python -m pytest -q -p no:cacheprovider eval/bok-reproduction/v1/tests
/tmp/statbridge-bok-venv/bin/python eval/bok-reproduction/v1/scripts/evaluate.py manifest
/tmp/statbridge-bok-venv/bin/python eval/bok-reproduction/v1/scripts/evaluate.py validate
/tmp/statbridge-bok-venv/bin/python eval/table-discovery/v4.1/scripts/validate_v41.py
cd src/agent/frontend && pnpm build
```

평가 산출물은 허용된 `.venv/cache/kosis-bok-reproduction/evaluation-v1/` 아래에만 생성한다. 비공개 평가 자료·원자료 CSV·API 키·유료 모델·실제 KOSIS는 사용하지 않는다. 검증 후 범위 파일만 Conventional Commit으로 기록하고 PR #45에 푸시한다.
