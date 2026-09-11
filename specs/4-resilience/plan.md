# Phase 4 — Resilience: Plan

**Goal**: The agent never breaks when `/quote` misbehaves.

---

## 1. Dependency

- [ ] 1.1 Run `uv add tenacity` (respects `add-bounds = "exact"`)

## 2. Config (`src/config.py`)

- [ ] 2.1 Change `quote_service_timeout` default from `30.0` to `10.0`
- [ ] 2.2 Add `quote_max_attempts: int = 3`
- [ ] 2.3 Add `quote_backoff_initial: float = 1.0`
- [ ] 2.4 Add `quote_backoff_max: float = 4.0`
- [ ] 2.5 Add `quote_slow_threshold: float = 2.0`

## 3. Quote Resilience Module (`src/quote/resilience.py`)

- [ ] 3.1 Define `_TransientQuoteError(Exception)` for timeouts, transport errors, 5xx/429
- [ ] 3.2 Define `is_transient(result, exc) -> bool`
  - `True`: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.RemoteProtocolError`,
    or `QuoteError.error == "upstream_unavailable"`
  - `False`: `cotacao_recusada` (422), `payload_invalido` (400), success
- [ ] 3.3 Define `post_quote_resilient(client, request, metrics: dict) -> QuoteResponse | QuoteError`
  - tenacity `AsyncRetrying` (3 attempts, exponential jitter 1→2→4, retry only on `_TransientQuoteError`)
  - mutates `metrics`: increments `attempts` per try, `retries` per backoff, records
    `latency_ms` on success, increments `slow_count` when latency > threshold
  - exhaustion → increments `failures`, returns `QuoteError(error="unavailable_after_retry", message=str(last_exc))`
  - business refusals pass through untouched (zero retries)
- [ ] 3.4 Define `get_planos_resilient(client) -> dict` — same retry policy on transport/timeout only;
  raises `_TransientQuoteError` on exhaustion

## 4. Agent Graph (`src/chat/agent.py`)

- [ ] 4.1 Add `metrics: dict` to `AgentState` TypedDict
- [ ] 4.2 `request_quote`: call `post_quote_resilient` / `get_planos_resilient`; seed and return `metrics`
- [ ] 4.3 `decide`:
  - `unavailable_after_retry` → "consultei mas o serviço está instável... posso tentar outro plano ou encaminhar para um atendente"
  - `slow_count > 0` or `retries > 0` → prepend brief acknowledgment ("demorou um pouquinho, mas consegui")
  - `cotacao_recusada` → next-plan auto-retry unchanged
  - preserve the `failures` counter in state for Phase 5 handoff trigger #3

## 5. Tests — Retry Policy (`tests/test_resilience.py`, `respx`, `@pytest.mark.anyio`)

- [ ] 5.1 503→502→200 → success, retries == 2
- [ ] 5.2 three 503s → `QuoteError("unavailable_after_retry")`
- [ ] 5.3 timeout then success → success, retries == 1
- [ ] 5.4 422 `cotacao_recusada` → exactly 1 HTTP call, not retried
- [ ] 5.5 `/planos` 500→503→200 → retries == 2
- [ ] 5.6 metrics dict after success-with-retry: `attempts==2, retries==1, failures==0`
- [ ] 5.7 metrics dict after exhaustion: `attempts==3, failures==1`
- [ ] 5.8 slow call (route callback `await asyncio.sleep`) → success, `slow_count==1`

## 6. Tests — Graceful Agent Responses (`tests/test_agent.py`)

Use `FakeQuoteClient(failure_rate=..., slow_rate=..., slow_seconds=...)` (constructor params).

- [ ] 6.1 slow (3s) success → reply contains delay acknowledgment
- [ ] 6.2 `unavailable_after_retry` → reply contains "outro plano" and "atendente"
- [ ] 6.3 immediate `cotacao_recusada` → next-plan retry, no retry-loop language

## 7. Lint & Format

- [ ] 7.1 `uv run ruff check --fix src/ tests/` — zero errors
- [ ] 7.2 `uv run ruff format src/ tests/` — no changes
- [ ] 7.3 `uv run pytest -m "not eval"` — all fast tests green