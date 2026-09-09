# Phase 2 — Agent Core: Requirements

## Scope

Phase 2 delivers a working LangGraph agent that converses with leads, extracts
qualification data, calls the quote service, and presents results. The agent replaces
the Phase 1 stub endpoint.

### In scope

| Component | What it does |
|---|---|
| `src/config.py` | Adds LLM config (OpenRouter API key, base URL, model) |
| `src/chat/schemas.py` | Adds `conversation_id` to ChatRequest |
| `src/chat/model.py` | Factory returning ChatOpenAI pointed at OpenRouter |
| `src/chat/prompt.py` | Build system prompt with persona, plan table, rules, 5 few-shot examples |
| `src/chat/tools.py` | `get_planos` and `cotar_seguro` agent tools wrapping QuoteClient |
| `src/chat/agent.py` | StateGraph with 4 nodes + conditional routing + compiled agent |
| `src/chat/router.py` | POST /chat invokes agent graph, returns final reply |
| `tests/` | Node-level tests, tool tests, e2e happy-path + refusal, few-shot validation |

### Graph Design

```
START → classify_intent ──[respond]──→ END
              │
         [qualify]
              │
        qualify_lead ──[respond]──→ END
              │
           [quote]
              │
       request_quote
              │
            decide ──[respond]──→ END
              │
          [retry] → request_quote
```

| Node | What it does | Route logic |
|---|---|---|
| `classify_intent` | LLM call: classify intent, extract lead data, generate simple replies | "respond" if greeting/question/decline; "qualify" otherwise |
| `qualify_lead` | Check if lead data is complete (age, vehicle_year, cep); if not, generate asking response | "quote" if complete; "respond" if missing data |
| `request_quote` | Call `cotar_seguro` tool; cache planos if not fetched yet | Always → `decide` |
| `decide` | LLM call: review quote result, present or auto-retry next plan | "respond" if success or all plans failed; "retry" if refusal with untried plans |

### Agent State (`AgentState`)

| Field | Type | Reducer | Purpose |
|---|---|---|---|
| `messages` | `list` | `operator.add` | Full conversation history (HumanMessage, AIMessage, ToolMessage) |
| `lead` | `dict` | overwrite | Extracted qualification data: age, veiculo_ano, cep, vehicle_model, data_inicio |
| `planos` | `dict \| None` | overwrite | Cached response from GET /planos |
| `quote` | `dict \| None` | overwrite | Latest quote result (QuoteResponse fields or error info) |
| `conversation_id` | `str` | overwrite | Thread ID for checkpointer |
| `tried_plans` | `list[str]` | `operator.add` | Plan IDs already attempted |
| `next` | `str` | overwrite | Routing decision for conditional edges |

### Tools

| Tool | Arguments | Returns |
|---|---|---|
| `get_planos()` | (none) | Formatted text: plan name, base price, deductible, coverages |
| `cotar_seguro(plano_id, idade, veiculo_ano, cep, data_inicio)` | Lead data | Formatted quote text or error message |

Both tools call the existing `QuoteClient` and return strings the LLM can use directly
in its responses.

### Out of scope

- Retry logic (tenacity, backoff, jitter) — Phase 3
- Human handoff/escalation — Phase 4
- Structured logging (structlog) — Phase 5
- PII detection/redaction — Phase 6
- SSE streaming — REST request/response only (SSE is future work)
- Custom checkpointer — MemorySaver only (enough for now)

---

## Design Decisions

### Decision 1: LLM-driven extraction (not regex)

**Why**: The lead provides data in natural language ("Tenho 35 anos", "meu carro é um
Honda Civic 2018"). Regex would be brittle (37 age representations, 4500+ vehicle models).
The LLM handles Portuguese variation naturally. Structured output via Pydantic ensures
typed extraction.

**How**: The `classify_intent` node returns a `ClassificationResult` with
`lead_update: dict` — any fields detected in the latest message.

### Decision 2: Deterministic `qualify_lead` (no LLM needed)

**Why**: Checking field presence is a simple dictionary inspection. The LLM already
extracted values in classify_intent. Adding another LLM call here wastes tokens and
latency. Only the "ask for missing data" path uses the LLM (to generate a natural
question).

### Decision 3: Auto-retry plans on refusal

**Why**: The quote service refuses based on age/vehicle/rules that are plan-independent
(e.g. age > 75 refused by all plans). But some refusals could be plan-specific (future
proofing). Trying all 3 plans before giving up is a better UX than asking the lead "want
to try another plan?" after every refusal. The `decide` node routes back to
`request_quote` until all plans are exhausted.

### Decision 4: MemorySaver for state persistence

**Why**: Each POST /chat call needs to continue the conversation from where it left off.
MemorySaver provides in-memory checkpointing with `thread_id = conversation_id`. No
external DB needed yet. Phase 5 will add a persistent checkpointer.

### Decision 5: Tools return strings, not Pydantic objects

**Why**: The LLM (and LangGraph tool system) works with string content for tool results.
The tools format QuoteResponse fields into natural Portuguese text. The structured data
(QuoteResponse) is stored in state.quote as a dict for programmatic access (e.g., the
decide node reads it to check for refusal).

### Decision 6: Few-shot from dataset, not external

**Why**: The dataset contains 712 "ganho" conversations with the exact same flow the agent
should replicate (WhatsApp, Portuguese, insurance domain). These are more representative
than hand-crafted examples. 5 examples fit within the few-shot token budget in the system
prompt.

### Decision 7: Flat `chat/` package for agent code

**Why**: The agent IS the chat domain's core logic. Adding a separate `src/agent/` package
would fragment the domain. New files (`agent.py`, `tools.py`, `prompt.py`, `model.py`) all
live under `src/chat/` alongside existing `schemas.py` and `router.py`.

### Decision 8: REST with conversation_id (not SSE)

**Why**: Simpler to implement and test. Each request is self-contained: send one message,
get one reply. The conversation_id links turns. Phase 5 can add SSE streaming as an
additional endpoint without changing the agent logic.

---

## Environmental Contract

| Variable | Default | Used by |
|---|---|---|
| `OPENROUTER_API_KEY` | (required, no default) | `src/chat/model.py` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | `src/chat/model.py` |
| `LLM_MODEL` | `openai/gpt-4o-mini` | `src/chat/model.py` |
| `QUOTE_SERVICE_URL` | `http://localhost:8000` | `src/quote/client.py` (existing) |
| `QUOTE_SERVICE_TIMEOUT` | `30.0` | `src/quote/client.py` (existing) |

---

## Dependencies to Add

| Package | Purpose | Group |
|---|---|---|
| `langchain>=1.0` | Agent framework | runtime |
| `langchain-core>=1.0` | Base types (messages, tools) | runtime |
| `langgraph>=1.0` | StateGraph, checkpointer | runtime |
| `langchain-openai` | ChatOpenAI for OpenRouter | runtime |

---

## Files Created/Modified

```
src/
├── config.py               # MODIFIED: add LLM env vars
├── chat/
│   ├── schemas.py          # MODIFIED: add conversation_id
│   ├── router.py           # MODIFIED: wire agent in place of stub
│   ├── model.py            # NEW: get_chat_model() factory
│   ├── prompt.py           # NEW: system prompt builder + few-shot
│   ├── tools.py            # NEW: get_planos, cotar_seguro
│   └── agent.py            # NEW: StateGraph, 4 nodes, compile

tests/
├── conftest.py             # MODIFIED: add mock_llm, agent fixtures
├── test_chat.py            # MODIFIED: test real agent reply
├── test_agent_tools.py     # NEW: tool unit tests
├── test_agent_graph.py     # NEW: node-level tests
├── test_agent_e2e.py       # NEW: end-to-end scenarios
└── test_few_shot.py        # NEW: few-shot extraction tests
```
