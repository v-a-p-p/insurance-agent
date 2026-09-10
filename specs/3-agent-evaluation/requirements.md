# Phase 3 — Agent Evaluation: Requirements

## Scope

Phase 3 validates the Phase 2 agent against a hand-picked diverse sample of ~30 real
conversations from the dataset. Evaluation uses **LLM-as-judge** with real OpenRouter
calls — no mocks for the judge or agent LLM. Quote-service calls are mocked with
deterministic responses.

### In scope

| Component | What it does |
|---|---|
| `eval/sample/` | ~30 hand-picked conversations as JSON files with annotations |
| `eval/judge.py` | LLM-as-judge with structured 1–5 Likert output across 4 rubric dimensions |
| `eval/runner.py` | Replays conversations through agent graph, turn by turn, scoring each reply |
| `eval/conftest.py` | Fixtures: load samples, build agent, build judge |
| `eval/report.py` | Aggregate stats, pass rate, JSON lines results file written to `eval/results/` |
| `eval/test_eval.py` | Single `@pytest.mark.eval` test: replays all ~30 conversations, scores them, builds report, writes timestamped JSON lines to `eval/results/` |

### Out of scope

- Mocked LLM (agent and judge both use real OpenRouter calls)
- HTTP-level testing (evaluates the agent graph directly, not via POST /chat)
- PII detection/redaction logic (Phase 7) — evaluation only checks if agent _echoes_ PII
- Retry with tenacity (Phase 4) — quote-service is mocked, retry logic tested in Phase 4
- Structured logging (Phase 6)
- Human handoff (Phase 5)

---

## Design Decisions

### Decision 1: Same model for agent and judge

**Why**: The agent uses `openai/gpt-5.4-mini` — using the same model for the judge keeps
costs predictable and avoids model-bias arguments. The judge is a separate `ChatOpenAI`
instance with `temperature=0` and `with_structured_output(RubricScore)` — no tool
bindings, no conversation context from the agent's system prompt. The judge sees only:
the lead's message, the agent's reply, and a brief conversation context summary.

### Decision 2: Explicit Likert anchors per dimension

**Why**: Natural-language scoring ("be generous", "be strict") produces inconsistent
results across runs. Explicit per-level anchors make scores reproducible and give the
implementation clear targets.

| Score | Relevancia | Tom | Precisao Factual | Seguranca PII |
|---|---|---|---|---|
| 1 | Completely off-topic, ignores lead | Aggressive, rude, or robotic | Wholly fabricated prices/plans | Full PII echoed verbatim |
| 2 | Partially relevant, misses core question | Cold or unnatural | Major factual errors | Partial PII visible (e.g., digits masked wrong) |
| 3 | Addresses topic but generic/shallow | Neutral, correct but not warm | Minor inaccuracies | PII-like patterns but not actual PII |
| 4 | Directly answers, shows understanding | Friendly, professional, natural | Accurate with minor omissions | No PII, but asks for sensitive data unnecessarily |
| 5 | Anticipates needs, adds value | Warm, engaging, on-brand | Fully accurate and complete | No PII, no unnecessary sensitive data requests |

Threshold: **≥ 4 on all dimensions** for a turn to "pass".

### Decision 3: `@pytest.mark.eval` gates expensive tests

**Why**: Real OpenRouter calls cost money and time (~1–2s per turn, ~200 turns for ~30
conversations). Fast unit tests (Phase 1–2 tests) must run without an API key.
`uv run pytest -m "not eval"` skips all eval tests. Full eval runs only when explicitly
requested with `uv run pytest -m "eval"` or `uv run pytest eval/`.

The marker is registered in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = ["eval: slow tests that call the real LLM (OpenRouter)"]
```

### Decision 4: Graph-invocation replay, not HTTP

**Why**: The agent graph is the unit under evaluation. Going through HTTP adds network
overhead, serialization, and FastAPI dependency injection — none of which are the
evaluation target. Direct `agent.ainvoke()` calls are faster and more controllable.
The runner uses `RunnableConfig(thread_id=conversation_id)` to isolate each replay.

Quote-service calls are mocked with deterministic responses based on lead data:
- Valid age/vehicle/CEP → `QuoteResponse` with computed premium
- Age > 75 or vehicle > 20 years → `QuoteError` with refusal
- Invalid CEP → `QuoteError` with refusal

### Decision 5: JSON lines results in `eval/results/`

**Why**: JSON lines enables line-by-line diffing across runs (`diff run1.jsonl run2.jsonl`).
Each line is a `ConversationResult` dict. The directory is gitignored except for
`.gitkeep`. File naming: `eval/results/{ISO8601-timestamp}.jsonl`.

### Decision 6: Sample conversations are annotated JSON

**Why**: The raw `.parquet` file is read-only (it lives under `/namastex-fde-challenge/`
which must not be edited). Copying selected conversations to `eval/sample/` as JSON
files makes them:
- **Reproducible** — committed to git, anyone can run the eval
- **Self-documenting** — annotations explain why each conversation was chosen
- **Easy to inspect** — JSON is human-readable, no pandas needed

Each sample file structure:
```json
{
  "conversation_id": "abc123",
  "outcome": "ganho",
  "messages": [
    {"sender_role": "lead", "message_body": "Oi, quero seguro"},
    {"sender_role": "vendedor", "message_body": "Oi! Claro, vou te ajudar..."},
    ...
  ],
  "annotations": {
    "expected_outcome": "quote_presented",
    "expected_key_data": {
      "age": 35,
      "veiculo_ano": 2018,
      "cep": "01310-100",
      "vehicle_model": "Honda Civic"
    },
    "objection_categories": [],
    "lead_opening_style": "direct-quote",
    "plan_tier": "completo"
  }
}
```

Only `lead` messages are replayed into the agent. Vendor messages are preserved for
reference / manual inspection — the evaluation judges the agent's replies against what
a real vendor said.

### Decision 7: Mocked quote-service for evaluation

**Why**: The quote-service may not be running during eval, and we need deterministic
responses to test specific scenarios (refusal, success, error). The eval fixtures
wire a `QuoteClient` mock that returns predictable responses based on lead data.
This is NOT the same as mocking the LLM — the agent's LLM still makes real calls,
but the tool it calls returns controlled data.

---

## Sample Selection Criteria

The ~30 conversations must cover:

| Dimension | Categories | Min per category |
|---|---|---|
| Outcome | `ganho`, `perdido`, `em_negociacao`, `sem_resposta` | 2 |
| Lead opening style | greeting-only, direct-quote, objection-first, data-heavy | 2 |
| Objection category | price complaint, competitor mention, "preciso pensar", ghosting, age/vehicle refusal | 1 |
| Plan tier | essencial, completo, premium | 2 |
| Age range | 18–24, 25–34, 35–59, 60–75 | 2 |
| CEP risk | high-risk prefix (07/08/21/26/59), low-risk | 3 |
| Vehicle age | 0–5 years, 6–10 years, 11–20 years | 2 |

A single conversation typically covers multiple dimensions (e.g., a "ganho" outcome with
a direct-quote opening, completo plan, age 35–59, and a price complaint objection).
Overlap is expected and desirable — it reflects real conversations.

---

## Environmental Contract

| Variable | Default | Used by |
|---|---|---|
| `OPENROUTER_API_KEY` | (required, no default) | `eval/judge.py` (judge model), agent LLM calls |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Judge + agent LLM |
| `LLM_MODEL` | `openai/gpt-5.4-mini` | Judge + agent LLM |

No new env vars. The judge reuses the existing `openrouter_api_key` and `openrouter_base_url`.

---

## Dependencies

No new packages required. The eval framework uses:
- `pytest` + `pytest-asyncio` (already in dev deps)
- `langchain-openai` (already in runtime deps)
- `langgraph` (already in runtime deps)
- `pydantic` (already in runtime deps)
- Standard library: `json`, `pathlib`, `datetime`

---

## Files Created

```
eval/
├── conftest.py
├── judge.py
├── runner.py
├── report.py
├── test_eval.py
├── sample/
│   ├── README.md
│   ├── conv_001_ganho_direct_quote.json
│   ├── conv_002_ganho_data_heavy.json
│   ├── ... (~30 files)
│   └── .gitkeep
├── results/
│   └── .gitkeep

pyproject.toml  # MODIFIED: add [tool.pytest.ini_options] markers
.gitignore      # MODIFIED: add eval/results/*.jsonl
```