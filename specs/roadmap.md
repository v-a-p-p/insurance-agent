# Roadmap

Phases are intentionally small — each one is a shippable slice of work, independently
reviewable and testable.

---

## Phase 1 — Foundation [DONE]

**Goal**: Project scaffold, quote-service integration, and Pydantic schemas.

- `src/` package structure following FastAPI best practices (domain-driven layout).
- Pydantic models: `Lead`, `QuoteRequest`, `QuoteResponse`, `QuoteError`.
- `POST /chat` endpoint (skeleton) and `GET /health`.
- `httpx` client for quote-service with timeout configuration.
- Tests: quote-service mock, schema validation, `/health` endpoint.
- Dataset loader: read `/namastex-fde-challenge/dataset/conversations.parquet`, group messages by `conversation_id`.

---

## Phase 2 — Agent Core [DONE]

**Goal**: Working conversational agent that qualifies the lead and produces a quote.

- LangGraph state graph: nodes for `classify_intent`, `qualify_lead`, `request_quote`, `decide`.
- OpenAI chat model via OpenRouter (`langchain-openai` with custom `base_url`).
- Tool: `get_planos` (reads from `/planos` endpoint).
- Tool: `cotar_seguro` (calls `POST /quote`).
- System prompt with few-shot examples extracted from `/namastex-fde-challenge/dataset/conversations.parquet`.
- Agent extracts from conversation: age, vehicle year/model, CEP, desired start date.
- Tests: mock LLM responses, end-to-end happy path with mocked quote-service.

---

## Phase 3 — Agent Evaluation

**Goal**: Validate the Phase 2 agent against a hand-picked diverse sample of real
conversations from the dataset using **LLM-as-judge** — real OpenRouter calls,
no mocks.

**Dataset sample**: ~30 conversations hand-picked from the dataset
(`/namastex-fde-challenge/dataset/conversations.parquet`) covering maximum outcome
diversity — all 4 outcomes (`ganho`, `perdido`, `em_negociacao`, `sem_resposta`),
all 4 lead opening styles, all 5 objection categories, all 3 plan tiers, and varied
age/CEP/vehicle combinations. The selected conversations are copied into
`eval/sample/` for reproducibility, with a note indicating their source.

- `eval/` directory with a pytest-based evaluation framework.
- `eval/sample/`: hand-picked conversation transcripts copied from the dataset,
  annotated with expected outcomes and key data points.
- `eval/judge.py`: LLM-as-judge module — calls the same OpenRouter model to score
  the agent's replies on a rubric (relevance, tone, factual accuracy, PII safety)
  using a 1–5 Likert scale, with 4+ threshold for pass. Returns structured scores
  via Pydantic.
- `eval/runner.py`: replays selected conversations through the agent graph, turn by
  turn, capturing agent replies for judgment.
- `eval/conftest.py`: fixtures to load the sample conversations and the judge model.
- Qualification extraction tests: judge scores whether the agent correctly extracts
  age, CEP, vehicle-year from varied Portuguese formats.
- Graph routing tests: verify the graph follows the correct node path for each intent.
- Quote handling tests: judge scores quote presentation accuracy, refusal + auto-retry
  behavior, and whether prices are never invented.
- Objection handling tests: judge scores agent responses to price complaints, competitor
  mentions, "preciso pensar", and ghosting.
- PII safety tests: judge verifies the agent does not echo CPF/email/phone in replies.
- End-to-end conversation replays with judge evaluating the entire multi-turn interaction.
- Evaluation report: per-category 1–5 scores + overall pass rate, printed at end of run.
  Results persisted as JSON lines for diffing across runs.

**Out of scope**: Mocked LLM — evaluation uses real OpenRouter calls to assess
real agent quality.

---

## Phase 4 — Resilience

**Goal**: The agent never breaks when `/quote` misbehaves.

- `tenacity` retry decorator on quote calls: 3 attempts, exponential backoff (1s → 2s → 4s), jitter.
- Timeout of 10s per attempt.
- When quote is slow: agent tells the lead "estou consultando a cotação, um momento..."
- When quote fails after retries: agent offers to try a different plan or escalate.
- Metrics: track failure rate, retry count, latency per conversation.
- Tests: inject failures via `QUOTE_FAILURE_RATE`/`QUOTE_SLOW_RATE`, assert graceful responses.

---

## Phase 5 — Human Handoff

**Goal**: Clear, defensible escalation to a human operator.

- New graph node: `escalate_to_human`.
- Handoff triggers (explicitly documented):
  1. Quote refused (age > 75, vehicle > 20 years, invalid CEP).
  2. Lead explicitly asks to speak to a human.
  3. 3 consecutive quote-call failures (all retries exhausted).
  4. Insufficient data after 3 qualification rounds.
- Structured handoff summary for the human agent (lead info, what was tried, why escalated).
- Graph `interrupt()` at handoff node for human-in-the-loop approval.
- Specify the handoff prompt behavior precisely (what to persist to state, exact wording) — resolving the TODO left in `src/chat/prompt.py` from Phase 2.
- Tests: each trigger path, handoff summary format.

---

## Phase 6 — Observability

**Goal**: Full traceability — every action is logged and reconstructable.

- `structlog` configured with JSON rendering.
- `conversation_id` and `trace_id` injected into every log line.
- Each quote attempt logged with: attempt number, latency, status (success/retry/fail), plan ID.
- LangGraph checkpointing enabled (SQLite or in-memory for dev, configurable).
- Agent state snapshot stored at every graph transition.
- Tests: log output validation, checkpoint restore.

---

## Phase 7 — Data Sensitivity

**Goal**: PII is detected at the agent level and never leaked to logs or persisted.

- PII detector (regex) implemented as a **LangGraph node** that runs before any
  logging or state persistence: CPF, email, phone, license plate patterns.
- PII redaction before structured logging (e.g., `***123.***-**`).
- System prompt instructs the LLM to never echo full PII back in conversation responses
  and to avoid storing raw sensitive data in agent state longer than needed for the quote.
- Validation: run the full dataset through the detector, confirm no leaks in logs.
- Tests: PII in message body → masked in logs, not persisted in plaintext.

---

## Phase 8 — Polish & Docs

**Goal**: Everything documented, tested end-to-end, ready for submission.

- `README.md` with: setup instructions, architecture diagram (Mermaid), decision log,
  how to run, how to test, how to read logs.
- Log of a complete execution (real conversation transcript, start to finish, with quote).
- `ai-logs/` directory populated with exported AI conversations.
- End-to-end test: real quote-service via Docker, full conversation flow, asserts on
  final state.
- Code cleanup pass: consistent naming, no dead code, `ruff check --fix && ruff format`.