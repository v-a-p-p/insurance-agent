# Tech Stack

## Core

| Layer | Choice | Rationale |
|---|---|---|
| **Runtime** | Python 3.14+ | Already in `pyproject.toml` |
| **API layer** | FastAPI 0.115+ | Async-native, Pydantic v2, team standard |
| **Agent orchestration** | LangGraph (`langgraph`) | State graphs with interrupts for human-in-the-loop, built-in checkpointing for traceability, fits the conversation → qualify → quote → decide flow |
| **LLM** | OpenAI-compatible via OpenRouter (`https://openrouter.ai/api/v1`) | Provider-agnostic abstraction; `OPENROUTER_API_KEY` env var; LangChain chat model integration (`langchain-openai`); structured output with Pydantic |
| **Async HTTP client** | `httpx` | Recommended by FastAPI guide; built-in timeout/retry; `ASGITransport` for testing |
| **Retry / resilience** | `tenacity` | Exponential backoff + jitter for `/quote` calls |
| **Schemas** | Pydantic v2 | Lead data, quote request/response, agent state, structured LLM output |
| **Chat model integration** | `langchain-openai` | OpenAI-compatible chat model pointed at OpenRouter base URL |
| **Structured logging** | `structlog` | JSON logs, trace-id per conversation |

## Data

| Tool | Purpose |
|---|---|
| `pandas` + `pyarrow` | Read `/namastex-fde-challenge/dataset/conversations.parquet` for few-shot prompt examples and agent evaluation |
| LangGraph MemoryStore / Checkpointer | Conversation state, quote history, and handoff context; no relational DB needed |

## Testing

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | Test runner |
| `httpx.AsyncClient` + `ASGITransport` | In-process FastAPI tests (no deprecated `async_asgi_testclient`) |
| `app.dependency_overrides` | Swap dependencies in tests |

## Tooling

| Tool | Purpose |
|---|---|
| `uv` | Package management (already configured, `add-bounds = "exact"`) |
| `ruff` | Lint + format (replaces black, isort, flake8) |
| Docker | Run quote-service locally via `docker compose` |

## What We Are Not Using

| Technology | Why Not |
|---|---|
| Relational DB (SQLAlchemy) | Agent state lives in LangGraph checkpointer; no persistence needed beyond that |
| RAG / Vector DB | The dataset is ~2,500 conversations — small enough for few-shot prompting, not semantic search |
| Frontend SPA (React/Vue) | Focus is the agent; any UI will be minimal (SSE feed or CLI) |
| `python-jose` | Unmaintained — use `PyJWT` if JWT is ever needed |
| `celery` / `arq` | Overkill for this scope; `tenacity` handles quote retries inline |