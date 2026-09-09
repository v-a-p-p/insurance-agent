# Phase 1 — Foundation: Requirements

## Scope

Phase 1 delivers a working project scaffold that can import datasets, talk to the
quote-service, and accept incoming chat requests. The agent logic is **not** included —
that's Phase 2.

### In scope

| Component | What it does |
|---|---|
| `src/config.py` | Loads `QUOTE_SERVICE_URL`, `QUOTE_SERVICE_TIMEOUT` from env / `.env` |
| `src/chat/schemas.py` | `ChatRequest` / `ChatResponse` / `Lead` Pydantic models |
| `src/chat/router.py` | `POST /chat` → returns `{"reply": "hello"}` (placeholder for Phase 2) |
| `src/quote/schemas.py` | `QuoteRequest`, `QuoteResponse`, `QuoteError` matching the legacy API |
| `src/quote/client.py` | Async httpx client for `GET /planos` and `POST /quote` |
| `src/dataset/schemas.py` | `ConversationMessage` and `Conversation` Pydantic models |
| `src/dataset/loader.py` | Reads `.parquet`, groups + sorts messages per conversation |
| `src/main.py` | FastAPI app, mounts chat router, health endpoint |
| `tests/` | Health, chat skeleton, schema validation, quote-client mock, dataset loader |

### Out of scope

- LLM integration (Phase 2)
- LangGraph state graphs (Phase 2)
- Retry / resilience logic (Phase 3)
- Human handoff (Phase 4)
- Structured logging / observability (Phase 5)
- PII detection (Phase 6)

---

## Design Decisions

### Decision 1: Domain-driven package layout

**Why**: The FastAPI best-practices guide (`AGENTS.md`) mandates domain-driven layout.
Three domains:

- `chat/` — the conversational interface (schemas, router)
- `quote/` — integration with the legacy quote service (schemas, client)
- `dataset/` — conversation history loader (schemas, loader)

### Decision 2: QuoteResponse is an explicit Pydantic model, not a loose dict

**Why**: The quote service is a documented API. Typing the response ensures no field is
missed when the agent (Phase 2) presents the quote to the lead. Registration fields from
`/quote` (premio_mensal, franquia, coberturas, carencia, multiplicadores) are all typed.

### Decision 3: QuoteClient as a dependency

**Why**: FastAPI dependency injection enables swapping the client in tests via
`app.dependency_overrides` without monkeypatching. The client is a thin wrapper around
`httpx.AsyncClient` with context-manager lifecycle.

### Decision 4: Dataset loader returns Pydantic models, not raw pandas

**Why**: Consistent with the rest of the codebase. The loader does the I/O and
transformation boundary; consumers (Phase 2+) receive typed domain objects.

### Decision 5: POST /chat returns `{"reply": "hello"}`

**Why**: Phase 1 is infrastructure-only. The endpoint exists so tests and the health
check pipeline validate end-to-end wiring. The real agent replaces this in Phase 2.

### Decision 6: Tests at repo root `tests/`

**Why**: Co-located tests (`src/**/__tests__`) add noise to the domain packages and
complicate `ruff` configuration. A flat `tests/` directory with domain-named files is
simpler and matches the FastAPI best-practices guide (`ASGITransport` + `AsyncClient`).

---

## Environmental Contract

| Variable | Default | Used by |
|---|---|---|
| `QUOTE_SERVICE_URL` | `http://localhost:8000` | `src/quote/client.py` |
| `QUOTE_SERVICE_TIMEOUT` | `30.0` | `src/quote/client.py` |

---

## Dependencies to Add

| Package | Purpose | Group |
|---|---|---|
| `httpx>=0.27` | Async HTTP client (quote-service, tests) | runtime |
| `pandas` | Read `.parquet` dataset | runtime |
| `pyarrow` | Parquet backend for pandas | runtime |
| `pydantic-settings>=2.4` | BaseSettings from env | runtime |
| `pytest` | Test runner | dev |
| `pytest-asyncio` | async test support | dev |
| `ruff>=0.6` | Lint + format | dev |

---

## Files Created

```
src/
├── __init__.py
├── main.py
├── config.py
├── chat/
│   ├── __init__.py
│   ├── schemas.py
│   └── router.py
├── quote/
│   ├── __init__.py
│   ├── schemas.py
│   └── client.py
└── dataset/
    ├── __init__.py
    ├── schemas.py
    └── loader.py

tests/
├── __init__.py
├── conftest.py
├── test_health.py
├── test_chat.py
├── test_schemas.py
├── test_quote_client.py
└── test_dataset.py
```