# Selective Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Import only the old MCP, Backend, Agent, and Frontend parts needed to show real table search candidates from current data.

**Architecture:** Keep Backend and Agent packages under `src/backend` and `src/agent`. Read the existing `data/tables` and a small copied metadata index. A small HTTP bridge serves candidate results to the React UI; numeric data is outside this search milestone.

**Tech Stack:** Python 3.12, pandas, requests, MCP SDK, React, Vite, TypeScript.

---

### Task 1: Backend and MCP

**Files:** Create `src/backend/statbridge_mcp/*.py`, `src/backend/server.py`, `src/backend/requirements.txt`, `data/processed/bok_*.csv`; modify `src/backend/statbridge_mcp/config.py`.

1. Write a test that loads the current catalog and searches a known table without a KOSIS key; confirm it fails before import.
2. Copy the seven MCP package modules and server entrypoint from `ClaBi/main`; copy only three small metadata CSVs. Point defaults to this project's `data/processed` and `data/tables`.
3. Run the test; confirm 349 catalog records and a real candidate ID. Keep API fetch behavior covered by the imported code.

### Task 2: Agent search

**Files:** Create `src/agent/statbridge_agent/{__init__,models,hcx,tools,pipeline}.py`, `src/agent/statbridge_agent/nodes/{__init__,query_interpret,retrieve}.py`; modify `tools.py` Backend path.

1. Write an integration test for a deterministic interpreted query reaching the real Backend search.
2. Copy only search pipeline modules; point `InProcessTools` to `src/backend`.
3. Run the test and confirm the candidate ID comes from Backend, not the generator.

### Task 3: HTTP and Frontend

**Files:** Create `src/backend/query_api.py`, `src/agent/frontend/{package.json,pnpm-lock.yaml,index.html,vite.config.ts,tsconfig*.json,src/*}`; create `tests/test_query_api.py`.

1. Write an HTTP handler test for valid/empty requests and candidate fields; confirm it fails first.
2. Implement a small `POST /api/query` bridge for Backend search. Return candidate IDs, scores, paths, and an explicit search-only status.
3. Reuse the previous Vite/React scaffold and visual tokens; replace mock chart/result UI with a candidate list consuming the real endpoint.
4. Run Python tests, a local HTTP smoke request, and `pnpm build`.

### Task 4: Documentation and final verification

**Files:** Create `README.md`, update `docs/plans/2026-09-26-selective-import-design.md` only if observed behavior differs.

1. Document installation, Backend API, MCP server, and Frontend run commands plus current limitations.
2. Re-run all imported tests and `golden-set-v3` validation. Check that no `.env`, virtual environment, duplicate 347 CSV, or old evaluation files were copied.

This workspace has no `.git` directory; the plan's commit steps cannot run here.
