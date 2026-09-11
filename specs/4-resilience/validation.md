# Phase 4 — Resilience: Validation

## How to know Phase 4 is done

Run each check in order.

---

### Check 1: tenacity is installed

```bash
uv run python -c "import tenacity; print(tenacity.__version__)"
```

**Expected**: prints a version, no `ModuleNotFoundError`.

---

### Check 2: settings reflect the resilience contract

```bash
uv run python -c "
from src.config import settings
assert settings.quote_service_timeout == 10.0
assert settings.quote_max_attempts == 3
assert settings.quote_backoff_initial == 1.0
assert settings.quote_backoff_max == 4.0
assert settings.quote_slow_threshold == 2.0
print('settings OK')
"
```

**Expected**: `settings OK`.

---

### Check 3: retry policy + counters

```bash
uv run pytest tests/test_resilience.py -v
```

**Expected**: 8 tests pass — transient retry, exhaustion, timeout retry,
business-refusal no-retry, `get_planos` retry, metrics-on-success,
metrics-on-exhaustion, slow flag.

---

### Check 4: business refusal is never retried

```bash
uv run pytest tests/test_resilience.py -v -k "refusal"
```

**Expected**: passes, asserting exactly 1 HTTP call.

---

### Check 5: slow + failed quotes produce graceful agent replies

```bash
uv run pytest tests/test_agent.py -v -k "slow or exhausted or refusal"
```

**Expected**: sluggish-success reply contains a delay ack; exhausted reply offers
"outro plano" and "atendente"; refusal still auto-retries the next plan.

---

### Check 6: full fast suite stays green

```bash
uv run pytest -m "not eval"
```

**Expected**: all Phase 1–4 fast tests pass, zero eval tests collected.

---

### Check 7: lint & format clean

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

**Expected**: exit 0, no changes.

---

### Check 8: live smoke against the real (unstable) service — optional

Starts the challenge service (20% failure / 10% slow) and confirms retries absorb
real failures without an unhandled exception.

```bash
docker compose -f namastex-fde-challenge/docker-compose.yml up --build -d
uv run python -c "
import asyncio
from src.quote.client import QuoteClient
from src.quote.resilience import post_quote_resilient
from src.quote.schemas import QuoteRequest

async def main():
    async with QuoteClient(base_url='http://localhost:8000', timeout=10.0) as c:
        m = {}
        r = await post_quote_resilient(c, QuoteRequest(plano_id='completo', idade=35, veiculo_ano=2022, cep='01310-100'), m)
        print(type(r).__name__, m)
asyncio.run(main())
"
docker compose -f namastex-fde-challenge/docker-compose.yml down
```

**Expected**: returns a `QuoteResponse` or an explicit `QuoteError`
(`unavailable_after_retry`) — never an unhandled exception — across several runs.
`m` shows `attempts >= 1` and retries consistent with the 20% failure rate.