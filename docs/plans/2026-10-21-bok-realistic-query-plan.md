# 한국은행 업무형 질의 재작성 실행 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 활성 BOK 평가셋 42개 사용자 질의를 통계 자료 작성자의 재현·갱신 업무에 현실적으로 맞추고, 기대 계열·기간·오라클과 의미상 일치시킨다.

**Architecture:** 사례별 질의는 `scripts/build.py`에서 명시적으로 작성한다. 파일럿 정답 계약 12건과 canonical v1은 유지하고, 기간 변형 6건은 최신 이용 가능 관측 기준을 분명히 한다. 보완 시나리오의 초기 화면·질의·숫자 오라클은 같은 작업을 나타내며 로컬 캐시에만 정답 수치를 둔다.

**Tech Stack:** Python 3, JSONL, existing `core.py` scorer, pytest.

---

### Task 1: 의미상 일치 회귀 테스트 작성

**Files:**
- Modify: `eval/bok-reproduction/v1/tests/test_evaluation.py`

**Step 1: 테스트 추가**

- canonical 12건의 기대 계약이 활성 파일럿에서 불변인지 검사한다.
- 파일럿 12개 `original_id`별 사용자 표현이 기대 통계 주제를 나타내고 기존 오매핑 키워드(주택가격/국제수지/소비자심리 등)가 잘못 붙지 않는지 검사한다.
- 여섯 기간 변형의 질의·기대 기간·reference date가 짝을 이루며 상대기간 기준이 “이용 가능한 최신 3관측월”로 고정되는지 검사한다.
- 보완 24건은 후속 대화의 초기 맥락과 실제 요청이 일치하고, summary_style-02의 오라클이 대기업·중소기업 대출금리 두 계열 및 차이를 포함하는지 검사한다.

**Step 2: RED 확인**

Run: `/tmp/statbridge-bok-venv/bin/python -m pytest -q -p no:cacheprovider eval/bok-reproduction/v1/tests`

Expected: 현재 잘못된 파일럿 질의, 상대기간 문구, summary_style-02 오라클 연결을 지적하는 테스트 실패.

### Task 2: 업무형 파일럿 질의 작성

**Files:**
- Modify: `eval/bok-reproduction/v1/scripts/build.py`
- Regenerate: `eval/bok-reproduction/v1/pilot.jsonl`

**Step 1: 사례별 질의 정리**

- 각 원본 사례의 공개 통계 주제와 period contract를 읽고 보도자료·표·그림 갱신 업무 문장으로 작성한다.
- 내부 코드·분류 ID·내부 카탈로그 라벨은 질문에 넣지 않는다.
- 추가 6건의 최근 3개월 질문은 “이용 가능한 최신 3개 관측월”을 뜻한다고 명시한다.

**Step 2: 생성 및 회귀 확인**

Run: `/tmp/statbridge-bok-venv/bin/python eval/bok-reproduction/v1/scripts/build.py --cache /mnt/c/users/cheon/orca/statbridge-local/.venv/cache/kosis-bok-reproduction`

Expected: audit 46, pilot 18, supplemental 24; canonical 12 expectations unchanged.

### Task 3: 보완 맥락·수치 오라클 정렬

**Files:**
- Modify: `eval/bok-reproduction/v1/scripts/build.py`
- Modify: `eval/bok-reproduction/v1/scripts/core.py` only if existing narrative-claim interface needs a small extension
- Regenerate: `eval/bok-reproduction/v1/supplemental.jsonl`
- Local only: `.venv/cache/kosis-bok-reproduction/evaluation-v1/oracles.json`

**Steps:**

1. Summary/report/followup initial context가 대상 계열과 업무를 제공하는지 확인한다.
2. summary_style-02는 실제 frozen provider 대기업·중소기업 대출금리 계열을 사용하고, 최신 계열값과 동일 시점 금리차를 독립 오라클 claim으로 만든다.
3. recovery-03은 대상 통계를 질의에 포함하고 자료 부재 fault는 그대로 둔다.
4. 정량 오라클과 사용자에게 표시된 수치 검증 테스트를 실행한다.

### Task 4: 검증 문서와 PR 갱신

**Files:**
- Modify: `eval/bok-reproduction/v1/README.md`
- Modify: `eval/bok-reproduction/v1/VALIDATION.md`
- Modify: `eval/bok-reproduction/v1/ANALYSIS.md` only if the relative-period basis wording changes
- Modify: `eval/bok-reproduction/v1/manifest.json`
- PR: #45, keep draft

Run:

```bash
/tmp/statbridge-bok-venv/bin/python -m pytest -q -p no:cacheprovider eval/bok-reproduction/v1/tests
/tmp/statbridge-bok-venv/bin/python eval/bok-reproduction/v1/scripts/evaluate.py manifest
/tmp/statbridge-bok-venv/bin/python eval/table-discovery/v4.1/scripts/validate_v41.py
cd src/agent/frontend && pnpm build
```

Confirm no paid model/KOSIS calls, no oracle values outside ignored cache, no unrelated user files staged, then commit with Conventional Commits and update PR #45 without marking it ready.
