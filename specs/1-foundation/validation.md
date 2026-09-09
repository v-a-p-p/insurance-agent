# Phase 1 — Foundation: Validation

## How to know Phase 1 is done

Each check below is self-contained. Run them in the order listed.

---

### Check 1: App loads

```bash
uv run python -c "from src.main import app; print(app.title)"
```

**Expected**: prints `AutoSeguro Agent` (no import errors, no missing deps).

---

### Check 2: Health endpoint

```bash
uv run uvicorn src.main:app --port 8001 &
curl -s http://localhost:8001/health | python -m json.tool
kill %1
```

**Expected**: `{"status": "ok"}` and HTTP 200.

---

### Check 3: Chat endpoint (skeleton)

```bash
uv run uvicorn src.main:app --port 8001 &
curl -s -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "anything"}' | python -m json.tool
kill %1
```

**Expected**: `{"reply": "hello"}` and HTTP 200.

---

### Check 4: Schemas validate good data

```python
from src.chat.schemas import ChatRequest, Lead
from src.quote.schemas import QuoteRequest, QuoteResponse

# ChatRequest with message only
r = ChatRequest(message="Oi, quero seguro")
assert r.message == "Oi, quero seguro"
assert r.lead is None

# ChatRequest with lead
r2 = ChatRequest(message="Meu carro é um Sandero 2022",
                  lead=Lead(name="Bruno", age=30, cep="07624-954"))
assert r2.lead.name == "Bruno"
assert r2.lead.age == 30

# QuoteRequest
qr = QuoteRequest(plano_id="completo", idade=35, veiculo_ano=2022, cep="01310-100")
assert qr.plano_id == "completo"

# QuoteResponse from dict
qr_dict = {
    "plano_id": "completo", "plano_nome": "Completo",
    "premio_mensal": 240.89, "franquia": 3000,
    "coberturas": ["colisao", "roubo", "furto"],
    "multiplicadores": {"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
    "carencia": {"coberturas": ["roubo", "furto"], "dias": 30, "observacao": "..."},
    "moeda": "BRL"
}
qr_response = QuoteResponse(**qr_dict)
assert qr_response.premio_mensal == 240.89
```

**Expected**: all assertions pass.

---

### Check 5: Schemas reject bad data

```python
from pydantic import ValidationError
from src.quote.schemas import QuoteRequest

try:
    QuoteRequest(plano_id="completo", idade=-1, veiculo_ano=2022)
    assert False, "Should have raised"
except ValidationError:
    pass  # good

try:
    QuoteRequest(plano_id="completo", idade=35, veiculo_ano=1800)
    assert False, "Should have raised"
except ValidationError:
    pass  # good

try:
    QuoteRequest(idade=35, veiculo_ano=2022)  # missing plano_id
    assert False, "Should have raised"
except ValidationError:
    pass  # good
```

**Expected**: all three raise `ValidationError`.

---

### Check 6: Dataset loader

```python
from src.dataset.loader import load_conversations
from src.dataset.schemas import Conversation, ConversationMessage

convs = load_conversations()
assert len(convs) > 0
assert all(isinstance(c, Conversation) for c in convs)
assert all(isinstance(m, ConversationMessage) for m in convs[0].messages)

# Check ordering
for conv in convs[:5]:
    indices = [m.message_index for m in conv.messages]
    assert indices == sorted(indices), f"Messages not sorted in {conv.conversation_id}"
```

**Expected**: loads ~2,500 conversations, all messages sorted.

---

### Check 7: All tests pass

```bash
uv run pytest -v
```

**Expected**: all tests green, zero skipped.

---

### Check 8: Lint & format clean

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

**Expected**: both commands exit 0 with no output changes.