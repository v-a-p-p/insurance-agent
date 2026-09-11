# Phase 4 — Resilience: Requirements

## Scope

Phase 4 makes the agent resilient to the unreliable legacy quote service
(20% failure, 10% slow by default). Transient failures retry with backoff;
slowness is acknowledged inline; exhausted retries degrade gracefully.
Per-conversation counters (attempts, retries, failures, latency, slow count)
live in the graph state.

### In scope

| Component | What it does |
|---|---|
| `src/quote/resilience.py` | tenacity retry policy + transient-error classification + counter updates |
| `src/config.py` | 10s timeout, 3 attempts, backoff limits, slow threshold |
| `src/chat/agent.py` | resilient `request_quote`; graceful `decide`; `metrics: dict` in state |
| `tests/test_resilience.py` | retry-policy + counter unit tests via `respx` |
| `tests/test_agent.py` | graceful-response tests via deterministic `FakeQuoteClient` |

### Out of scope

- Human-handoff node (Phase 5) — Phase 4 only *offers* escalation in reply text
- Metrics aggregation / failure-rate reporting / HTTP `/metrics` (Phase 6)
- Structured logging / JSON logs (Phase 6)
- PII detection (Phase 7)
- Live-service integration tests (Phase 8 e2e)

---

## Design Decisions

### Decision 1: Retry only transient failures, never business refusals

`/quote` 5xx/timeout = transient, may succeed on retry. 422 `cotacao_recusada`
(age > 75, vehicle > 20) is a *correct* answer — retrying wastes calls and never
succeeds. Only the former is retried; business refusals pass through to
plan-switching.

### Decision 2: tenacity `AsyncRetrying` with exponential jitter

3 attempts, backoff 1s→2s→4s with jitter (avoids thundering herd). Applied in
`src/quote/resilience.py`, adjacent to the client, keeping the graph node readable.

### Decision 3: Single-reply slow acknowledgment (no API change)

The lead sees the reply only after the call returns. Rather than change the `/chat`
contract (SSE / interim messages = larger change), `decide` detects `slow_count > 0`
or `retries > 0` and prepends "demorou um pouquinho, mas consegui sua cotação!".
The 8s mock slow call completes within the 10s timeout, so it is flagged *slow*,
not failed.

### Decision 4: Plain dict counters in state, no metrics collector

`metrics: dict` in `AgentState`, mutated in place by `resilience.py`. This is all
Phase 4 behavior needs (slow-ack signal, escalation wording) and all Phase 5 needs
(`failures` counter for the "3 consecutive quote failures" trigger). Failure-rate
aggregation, latency reporting, and structured logging are deferred to Phase 6,
which owns observability and will likely use `structlog` rather than a bespoke
singleton. No `metrics.py`, no `MetricsCollector`.

### Decision 5: Deterministic fake + respx (no live service in unit tests)

`respx` mocks the transport for retry-policy tests with exact 500/timeout sequences.
`FakeQuoteClient(failure_rate, slow_rate, slow_seconds)` drives agent-level response
tests deterministically. Live-service integration honoring the real
`QUOTE_FAILURE_RATE`/`QUOTE_SLOW_RATE` remains an optional Phase 8 e2e concern.

### Decision 6: Timeout 10s, slow threshold 2s

Roadmap specifies 10s per attempt. The mock's default slow call sleeps 8s (
completes, flagged slow); a true hang trips the 10s timeout → retry.

---

## Environmental Contract

| Variable | Default | Used by |
|---|---|---|
| `QUOTE_SERVICE_TIMEOUT` | `10.0` | per-attempt httpx timeout (was 30) |
| `QUOTE_MAX_ATTEMPTS` | `3` | retries |
| `QUOTE_BACKOFF_INITIAL` | `1.0` | backoff start |
| `QUOTE_BACKOFF_MAX` | `4.0` | backoff cap |
| `QUOTE_SLOW_THRESHOLD` | `2.0` | slow flag trigger |

`QUOTE_FAILURE_RATE` / `QUOTE_SLOW_RATE` / `QUOTE_SLOW_SECONDS` belong to the
challenge service (read-only). The agent never reads them; tests simulate them.

---

## Dependencies

- `tenacity` (new) — everything else already present (`httpx`, `pydantic`, `pytest`, `respx`)

---

## Files Created / Modified

```
src/quote/resilience.py        # NEW
src/config.py                  # MODIFIED (timeout 10s + resilience settings)
src/chat/agent.py              # MODIFIED (resilient quote + metrics state)
tests/test_resilience.py       # NEW
tests/test_agent.py            # MODIFIED (graceful-response tests)
pyproject.toml                 # MODIFIED via `uv add tenacity`
```