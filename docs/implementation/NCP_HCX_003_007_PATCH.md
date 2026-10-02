# StatBridge NCP HCX-003 / HCX-007 patch

## Runtime flow

```text
UI natural language
  -> HCX-003 statistical-language classifier
  -> v5 statistical-language dictionary
  -> ambiguity?
       yes -> HCX-007 phrased clarification + dictionary-owned buttons -> re-search
       no  -> dictionary-owned exact table/item/objL/prdSe
  -> MCP StatisticsService
  -> KOSIS API
  -> HCX-007 grounded final answer
  -> UI
```

## Model boundaries

### HCX-003
- Natural Korean -> statistical-language terms only.
- Produces concepts, subjects, measures, time/comparison/qualifier terms.
- It **cannot invent or select** `tblId`, `itmId`, `objL1..8`, or numeric data.
- Those identifiers always come from `stat_language_dictionary.json`.

### HCX-007
- Main conversational agent.
- Rephrases a dictionary-generated clarification question while preserving dictionary button options.
- After KOSIS returns rows, generates the final Korean answer using only those returned rows and the validated API plan.
- It does not replace the deterministic dictionary/API-ID validation layer.

## .env location

`.env`

Minimum settings:

```env
KOSIS_API_KEY=
NCP_CLOVA_API_KEY=

NCP_CLASSIFIER_MODEL=HCX-003
NCP_CLASSIFIER_API_VERSION=v1
# Optional override. Normally leave empty because HCX-003 uses the public v1 endpoint.
NCP_CLASSIFIER_URL=

NCP_MAIN_MODEL=HCX-007
NCP_MAIN_API_VERSION=v3
NCP_MAIN_THINKING_EFFORT=low
```

The client also accepts `NCP_API_KEY` or `CLOVA_STUDIO_API_KEY` as a fallback, but `NCP_CLOVA_API_KEY` is preferred.

## HCX model endpoints

HCX-003 uses CLOVA Studio Chat Completions v1 by default (`/v1/chat-completions/HCX-003`). HCX-007 uses Chat Completions v3 by default (`/v3/chat-completions/HCX-007`). `NCP_CLASSIFIER_URL` and `NCP_MAIN_URL` remain optional overrides.

## Tests

Offline orchestration test:

```bat
scripts/windows/RUN_AGENT_TEST.cmd
```

Real NCP model smoke test after keys are configured:

```bat
.venv\Scripts\python.exe tests/TEST_NCP_MODELS.py
```
