# Phase 1 — Foundation: Plan

**Goal**: Project scaffold, quote-service integration, and Pydantic schemas.

---

## 1. Dependencies

- [ ] 1.1 Add runtime dependencies via `uv add`:
  - `httpx` — async HTTP client for quote-service
  - `pandas` + `pyarrow` — read conversations.parquet
  - `pydantic-settings` — BaseSettings for env-driven config
- [ ] 1.2 Add dev dependencies via `uv add --group dev`:
  - `pytest` + `pytest-asyncio` — test runner
- [ ] 1.3 Add dev tool: `ruff` (lint + format) via `uv add --group dev ruff`

## 2. Config (`src/config.py`)

- [ ] 2.1 Create `Settings(BaseSettings)` with:
  - `QUOTE_SERVICE_URL: str = "http://localhost:8000"`
  - `QUOTE_SERVICE_TIMEOUT: float = 30.0`
  - `env_file = ".env"`, `extra = "ignore"`
- [ ] 2.2 Export singleton `settings = Settings()`.

## 3. Pydantic Schemas

### 3.1 Chat domain (`src/chat/`)
- [ ] 3.1.1 `src/chat/__init__.py` (empty)
- [ ] 3.1.2 `src/chat/schemas.py`:
  - `Lead` model: `name`, `age`, `cep`, `vehicle_model`, `vehicle_year`, `cpf` (all optional except `name`)
  - `ChatRequest`: `message: str`, `lead: Lead | None = None`
  - `ChatResponse`: `reply: str`

### 3.2 Quote domain (`src/quote/`)
- [ ] 3.2.1 `src/quote/__init__.py` (empty)
- [ ] 3.2.2 `src/quote/schemas.py`:
  - `QuoteRequest`: `plano_id`, `idade`, `veiculo_ano`, `cep`, `data_inicio` (mirrors quote-service schema)
  - `QuoteResponse`: all fields returned by successful `/quote` (premio_mensal, franquia, coberturas, multiplicadores, carencia, etc. — Pydantic model)
  - `QuoteError`: `error`, `message`/`motivo`/`detalhe`

### 3.3 Dataset domain (`src/dataset/`)
- [ ] 3.3.1 `src/dataset/__init__.py` (empty)
- [ ] 3.3.2 `src/dataset/schemas.py`:
  - `ConversationMessage`: maps to a single row (conversation_id, message_index, timestamp, sender_role, sender_name, message_type, message_body, channel, conversation_outcome, lead_idade_informada, veiculo_texto)
  - `Conversation`: wraps `conversation_id`, `outcome`, `messages: list[ConversationMessage]` (sorted by message_index)

## 4. API Endpoints

### 4.1 App entrypoint (`src/main.py`)
- [ ] 4.1.1 Create FastAPI app with lifespan, title `"AutoSeguro Agent"`
- [ ] 4.1.2 Include `chat.router` and `health` endpoint

### 4.2 Chat router (`src/chat/router.py`)
- [ ] 4.2.1 `POST /chat` accepts `ChatRequest`, returns `ChatResponse(reply="hello")` (skeleton)
- [ ] 4.2.2 `GET /health` lives in `src/main.py` directly

## 5. Quote-service Client (`src/quote/client.py`)

- [ ] 5.1 `QuoteClient` class wrapping `httpx.AsyncClient`:
  - `__init__` takes `base_url` and `timeout` from settings
  - `async get_planos()` → calls `GET /planos`, returns dict
  - `async post_quote(request: QuoteRequest)` → calls `POST /quote`, returns `QuoteResponse | QuoteError`
  - Context-manager support (`async with`)
- [ ] 5.2 Use `QuoteClient` as a FastAPI dependency via `Annotated` + closure or factory function

## 6. Dataset Loader (`src/dataset/loader.py`)

- [ ] 6.1 `load_conversations(path: Path) -> list[Conversation]`:
  - Reads `.parquet` with `pd.read_parquet`
  - Groups by `conversation_id`
  - Sorts each group by `message_index`
  - Returns list of `Conversation` Pydantic models
- [ ] 6.2 Path defaults to `/namastex-fde-challenge/dataset/conversations.parquet`

## 7. Package Setup

- [ ] 7.1 `src/__init__.py` (empty)
- [ ] 7.2 Verify `pyproject.toml` has no `[tool.uv.package]` (we don't ship a package, it's an app)

## 8. Tests (`tests/`)

- [ ] 8.1 `tests/__init__.py` (empty)
- [ ] 8.2 `tests/conftest.py`: shared `client` fixture (httpx + ASGITransport)
- [ ] 8.3 `tests/test_health.py`: GET /health → 200, `{"status": "ok"}`
- [ ] 8.4 `tests/test_chat.py`: POST /chat → 200, `{"reply": "hello"}`
- [ ] 8.5 `tests/test_schemas.py`:
  - Lead with valid data → validates
  - Lead missing required fields → validation error
  - QuoteRequest validation (e.g., idade >= 0, veiculo_ano reasonable)
- [ ] 8.6 `tests/test_quote_client.py`:
  - Mock quote-service with `respx` or manual httpx transport mock
  - Happy path: POST /quote → QuoteResponse
  - Error path: 422 → QuoteError (cotacao_recusada)
  - GET /planos → returns plans dict
- [ ] 8.7 `tests/test_dataset.py`:
  - Load conversations from the real parquet file
  - Assert correct grouping and ordering
  - Assert Pydantic model types

## 9. Lint & Format

- [ ] 9.1 Run `ruff check --fix src/ tests/` — zero errors
- [ ] 9.2 Run `ruff format src/ tests/` — no changes