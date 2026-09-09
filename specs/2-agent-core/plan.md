# Phase 2 — Agent Core: Plan

**Goal**: Working conversational agent that qualifies the lead and produces a quote.

---

## 1. Dependencies

- [ ] 1.1 Add runtime dependencies via `uv add`:
  - `langchain`, `langgraph`, `langchain-core`, `langchain-openai`
- [ ] 1.2 Verify `langchain>=1.0` and `langgraph>=1.0` (LangChain 1.0 LTS)

## 2. Config (`src/config.py`)

- [ ] 2.1 Add to `Settings`:
  - `openrouter_api_key: str = ""`
  - `openrouter_base_url: str = "https://openrouter.ai/api/v1"`
  - `llm_model: str = "openai/gpt-4o-mini"`
  - `agent_few_shot_count: int = 5`
  - `agent_recursion_limit: int = 25`

## 3. Chat Schemas Update (`src/chat/schemas.py`)

- [ ] 3.1 Add `conversation_id: str | None = None` to `ChatRequest`

## 4. LLM Factory (`src/chat/model.py`)

- [ ] 4.1 Create `get_chat_model() -> ChatOpenAI`:
  - Uses `openrouter_base_url` as `base_url`
  - Uses `openrouter_api_key` as `api_key`
  - Model from `llm_model`
  - `temperature=0.3`

## 5. System Prompt (`src/chat/prompt.py`)

- [ ] 5.1 Create `build_system_prompt() -> str`:
  - AutoSeguro agent persona: friendly, efficient, Portuguese-speaking
  - Goal: qualify leads, present insurance quotes
  - Available plans table (essencial/completo/premium with prices, deductibles, coverages)
  - Data to collect: age, vehicle model/year, CEP, start date
  - Instructions for each conversation phase: greeting → qualification → quote → decision
  - Quote refusal handling: auto-try next plan; if all 3 refused, explain why
  - Conversation examples (see 5.2)

- [ ] 5.2 Create `extract_few_shot_examples(n: int) -> list[dict]`:
  - Reads dataset, filters for `conversation_outcome == "ganho"`
  - Selects 5 conversations (newest / most informative)
  - Formats as WhatsApp-style transcripts: `[lead]: ...` / `[vendedor]: ...`
  - Embeds them into the system prompt

## 6. Tools (`src/chat/tools.py`)

- [ ] 6.1 Create `get_planos` tool:
  - `@tool` decorator with typed signature
  - Calls `QuoteClient.get_planos()`
  - Returns serialized plan options (name, base price, deductible, coverages)
  - No arguments needed (reads from quote service)

- [ ] 6.2 Create `cotar_seguro` tool:
  - `@tool` decorator with typed signature
  - Args: `plano_id: str`, `idade: int`, `veiculo_ano: int`, `cep: str | None = None`, `data_inicio: str | None = None`
  - Calls `QuoteClient.post_quote(QuoteRequest(...))`
  - If `QuoteResponse`: returns formatted premium + deductible + coverages text
  - If `QuoteError`: returns error text (refusal reason or technical error)
  - Does NOT retry (that's Phase 3)

## 7. Agent State (`src/chat/agent.py` — State definition)

- [ ] 7.1 Define `AgentState(TypedDict)`:
  - `messages: Annotated[list, operator.add]` — conversation history
  - `lead: dict` — extracted fields (age, veiculo_ano, cep, vehicle_model, data_inicio)
  - `planos: dict | None` — cached plan data from GET /planos
  - `quote: dict | None` — latest quote result
  - `conversation_id: str` — thread identifier
  - `tried_plans: Annotated[list[str], operator.add]` — plan IDs already attempted
  - `next: str` — routing decision for conditional edges

## 8. Agent Graph (`src/chat/agent.py` — Nodes & builder)

### 8.1 `classify_intent` node

- [ ] 8.1.1 LLM call with structured output model `ClassificationResult`
  - `ClassificationResult`: `intent: Literal["respond", "qualify"]`, `reply: str | None`, `lead_update: dict`
- [ ] 8.1.2 Merge `lead_update` into state.lead
- [ ] 8.1.3 Returns `{"messages": [AIMessage(content=reply)], "lead": ..., "next": intent}`

### 8.2 `qualify_lead` node

- [ ] 8.2.1 Deterministic check: are age, veiculo_ano, cep present in state.lead?
- [ ] 8.2.2 If complete: return `{"next": "quote"}`
- [ ] 8.2.3 If incomplete: LLM call to generate response asking for missing fields → return `{"next": "respond"}`

### 8.3 `request_quote` node

- [ ] 8.3.1 Determine which plan to try: default "completo", or next untried if retrying
- [ ] 8.3.2 Fetch planos if not cached (call `QuoteClient.get_planos()`)
- [ ] 8.3.3 Call `cotar_seguro()` with lead data from state
- [ ] 8.3.4 Store result in state.quote (QuoteResponse dict or QuoteError dict)
- [ ] 8.3.5 Append plan to `tried_plans`
- [ ] 8.3.6 Return `{"quote": ..., "planos": ..., "tried_plans": ..., "next": "decide"}`

### 8.4 `decide` node

- [ ] 8.4.1 LLM call: review quote result + conversation, decide next action
- [ ] 8.4.2 If quote success: format and present quote → `{"next": "respond"}`
- [ ] 8.4.3 If quote refused AND untried plan remains: auto-retry → `{"next": "retry"}`
- [ ] 8.4.4 If quote refused AND no untried plans: explain why → `{"next": "respond"}`
- [ ] 8.4.5 If quote error: generate error message → `{"next": "respond"}` (Phase 3 adds retry)

### 8.5 Routing & Compilation

- [ ] 8.5.1 Conditional edge from `classify_intent`: route "respond" → END, "qualify" → `qualify_lead`
- [ ] 8.5.2 Conditional edge from `qualify_lead`: "quote" → `request_quote`, "respond" → END
- [ ] 8.5.3 Static edge: `request_quote` → `decide`
- [ ] 8.5.4 Conditional edge from `decide`: "respond" → END, "retry" → `request_quote`
- [ ] 8.5.5 Compile with `MemorySaver()` checkpointer
- [ ] 8.5.6 Set `recursion_limit` from settings

### 8.6 Dependency

- [ ] 8.6.1 Create `build_agent(llm, quote_client) -> CompiledStateGraph` factory
- [ ] 8.6.2 Create `get_agent()` FastAPI dependency that wires `get_chat_model()` + `QuoteClient`

## 9. Router Update (`src/chat/router.py`)

- [ ] 9.1 Wire `get_agent` dependency into POST /chat
- [ ] 9.2 Replace stub: invoke agent graph with user message
- [ ] 9.3 Generate `conversation_id` (uuid4) if not provided in request
- [ ] 9.4 Build config with `thread_id = conversation_id`
- [ ] 9.5 If `request.lead` is provided, inject it into state (pre-seed lead fields)
- [ ] 9.6 Return last AI message content as `ChatResponse(reply=...)`

## 10. Tests

- [ ] 10.1 `tests/conftest.py`: add `mock_llm` fixture (manual monkeypatch), `agent` fixture (compiled graph with mocked LLM)
- [ ] 10.2 `tests/test_agent_tools.py`:
  - `get_planos` returns formatted plan list
  - `cotar_seguro` success → formatted quote text
  - `cotar_seguro` refusal → error text
- [ ] 10.3 `tests/test_agent_graph.py`:
  - `classify_intent`: greeting → respond route
  - `classify_intent`: quote request → qualify route
  - `qualify_lead`: complete data → quote route
  - `qualify_lead`: missing data → respond route
  - `request_quote`: stores QuoteResponse in state
  - `decide`: success → respond, refusal → retry
- [ ] 10.4 `tests/test_agent_e2e.py`:
  - Happy path: full conversation → successful quote
  - Refusal path: quote refused → auto-retry next plan → successful
  - All refused path: all 3 plans refused → graceful response
  - Missing data path: agent asks for needed fields
- [ ] 10.5 `tests/test_few_shot.py`:
  - `extract_few_shot_examples(5)` returns 5 formatted conversations
  - Each example contains lead and vendor messages
  - All examples are "ganho" outcome
- [ ] 10.6 Update `tests/test_chat.py`: endpoint returns agent-generated reply (not "hello")

## 11. Lint & Format

- [ ] 11.1 Run `ruff check --fix src/ tests/` — zero errors
- [ ] 11.2 Run `ruff format src/ tests/` — no changes
- [ ] 11.3 Run `uv run pytest -v` — all tests green
