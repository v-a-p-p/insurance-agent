# Phase 2 — Agent Core: Validation

## How to know Phase 2 is done

Each check is self-contained. Run them in order.

---

### Check 1: Dependencies resolve

```bash
uv run python -c "from langgraph.graph import StateGraph; from langchain_openai import ChatOpenAI; print('OK')"
```

**Expected**: prints `OK`, no ImportError.

---

### Check 2: System prompt builds

```bash
uv run python -c "
from src.chat.prompt import build_system_prompt
prompt = build_system_prompt()
assert 'AutoSeguro' in prompt
assert 'essencial' in prompt
assert 'lead:' in prompt.lower()
assert 'vendedor:' in prompt.lower()
print(f'Prompt built: {len(prompt)} chars')
"
```

**Expected**: prints prompt length > 2000 chars, contains persona, plan names, few-shot examples.

---

### Check 3: Few-shot extracts from dataset

```bash
uv run python -c "
from src.chat.prompt import extract_few_shot_examples
examples = extract_few_shot_examples(5)
assert len(examples) == 5
for e in examples:
    assert '[lead]:' in e or '[vendedor]:' in e
print('Few-shot: 5 examples extracted')
"
```

**Expected**: 5 examples, each formatted as WhatsApp-style transcript.

---

### Check 4: LLM model factory works

```bash
uv run python -c "
from src.chat.model import get_chat_model
model = get_chat_model()
assert model.model_name == 'openai/gpt-4o-mini'
assert 'openrouter.ai' in str(model.openai_api_base)
print(f'Model: {model.model_name}')
"
```

**Expected**: ChatOpenAI instance with correct model and base_url.

---

### Check 5: Tools work with mock quote service

```bash
uv run python -c "
from src.chat.tools import make_get_planos, make_cotar_seguro
print('Tool factories compile OK')
"
```

**Expected**: prints `Tool factories compile OK`.

---

### Check 6: Agent graph compiles

```bash
uv run python -c "
from unittest.mock import MagicMock, AsyncMock
from src.chat.agent import build_agent
mock_llm = MagicMock()
mock_quote_client = AsyncMock()
agent = build_agent(mock_llm, mock_quote_client)
print(f'Agent compiled: {type(agent).__name__}')
"
```

**Expected**: prints `Agent compiled: CompiledStateGraph` — no errors.

---

### Check 7: POST /chat returns agent reply

Start server:
```bash
uv run uvicorn src.main:app --port 8001 &
```

Send greeting:
```bash
curl -s -X POST http://localhost:8001/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Oi", "conversation_id": "manual-test-1"}' | python -m json.tool
```

**Expected**: JSON with `{"reply": ...}` where reply is a natural Portuguese greeting
from the agent.

Send qualification data:
```bash
curl -s -X POST http://localhost:8001/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Tenho 35 anos, meu carro é um Honda Civic 2018, e moro em 01310-100", "conversation_id": "manual-test-1"}'
```

**Expected**: Agent responds, possibly asking for missing data or offering a quote.

```bash
kill %1
```

---

### Check 8: Happy path e2e test passes

```bash
uv run pytest tests/test_agent_e2e.py -v
```

**Expected**: happy path test passes (full conversation flow with mocked LLM + mocked
QuoteClient).

---

### Check 9: Quote refusal → auto-retry works

```bash
uv run pytest tests/test_agent_e2e.py -v -k "refusal"
```

**Expected**: test passes — quote refused for first plan, auto-retries next plan,
eventually succeeds or explains all refused.

---

### Check 10: All tests green

```bash
uv run pytest -v
```

**Expected**: all tests green, zero skipped.

---

### Check 11: Lint & format clean

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

**Expected**: both commands exit 0 with no output changes.
