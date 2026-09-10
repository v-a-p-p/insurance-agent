# Phase 3 — Agent Evaluation: Plan

**Goal**: Validate the Phase 2 agent against a hand-picked diverse sample of real
conversations from the dataset using **LLM-as-judge** — real OpenRouter calls,
no mocks.

---

## 1. Eval Marker

- [ ] 1.1 Register `eval` marker in `pyproject.toml` under `[tool.pytest.ini_options]`
  - `markers = ["eval: slow tests that call the real LLM (OpenRouter)"]`
- [ ] 1.2 Ensure `uv run pytest -m "not eval"` skips all eval tests (fast CI path)

## 2. Sample Dataset (`eval/sample/`)

- [ ] 2.1 Hand-pick ~30 conversations from the dataset covering maximum diversity:
  - All 4 outcomes: `ganho`, `perdido`, `em_negociacao`, `sem_resposta`
  - All 4 lead opening styles (greeting-only, direct-quote, objection-first, data-heavy)
  - All 5 objection categories (price complaint, competitor mention, "preciso pensar",
    ghosting, age/vehicle refusal)
  - All 3 plan tiers (essencial, completo, premium)
  - Varied age ranges (18–24, 25–34, 35–59, 60–75), CEP prefixes (low/high risk), and
    vehicle years (0–5, 6–10, 11–20)
- [ ] 2.2 Copy selected conversations as JSON files into `eval/sample/` (one file per
  conversation). Each file includes:
  - `conversation_id` (from dataset)
  - `outcome` (from dataset)
  - `messages`: list of `{sender_role, message_body}` (lead/vendedor only)
  - `annotations`: `{expected_outcome, expected_key_data: {age, veiculo_ano, cep, vehicle_model},
    objection_categories: [str], lead_opening_style: str, plan_tier: str | None}`
- [ ] 2.3 Add a `eval/sample/README.md` noting the source dataset path and selection
  criteria for reproducibility.

## 3. Judge Module (`eval/judge.py`)

- [ ] 3.1 Define `RubricDimension` Pydantic model:
  - `score: int` (1–5 Likert scale)
  - `justificativa: str` (short justification in Portuguese)
- [ ] 3.2 Define `RubricScore` Pydantic model:
  - `relevancia: RubricDimension` — does the reply address what the lead asked?
  - `tom: RubricDimension` — is the tone friendly, professional, natural Portuguese?
  - `precisao_factual: RubricDimension` — are plan names/prices/coverages correct?
  - `seguranca_pii: RubricDimension` — does the reply leak CPF/email/phone?
- [ ] 3.3 Define explicit 1–5 anchors per dimension in the judge system prompt
- [ ] 3.4 Create `build_judge() -> ChatOpenAI`:
  - Same model as agent (`openai/gpt-5.4-mini`) via OpenRouter
  - `temperature=0` (deterministic scoring)
  - `with_structured_output(RubricScore)`
- [ ] 3.5 Create `judge_turn(judge, lead_msg: str, agent_reply: str, context: dict) -> RubricScore`:
  - Builds prompt with conversation context, lead message, agent reply
  - Invokes judge model, returns structured score

## 4. Runner (`eval/runner.py`)

- [ ] 4.1 Create `TurnResult` Pydantic model:
  - `turn_index: int`
  - `lead_message: str`
  - `agent_reply: str`
  - `rubric: RubricScore`
  - `graph_path: list[str]` — nodes visited during this turn
- [ ] 4.2 Create `ConversationResult` Pydantic model:
  - `conversation_id: str`
  - `annotations: dict`
  - `turns: list[TurnResult]`
  - `overall_rubric: RubricScore | None`
- [ ] 4.3 Create `async replay_conversation(agent, conversation: dict) -> ConversationResult`:
  - Reset agent state (new thread_id = conversation_id)
  - Replay each lead message sequentially: invoke agent graph, capture AIMessage reply
  - For each turn, record `graph_path` by inspecting state transitions (nodes visited)
  - Returns complete `ConversationResult` (without judge scores — those come after)
- [ ] 4.4 Create `async score_conversation(judge, result: ConversationResult) -> ConversationResult`:
  - For each turn, call `judge_turn()` with lead message + agent reply
  - Populate `rubric` on each `TurnResult`
- [ ] 4.5 Create `async run_replay(agent, judge, conversation) -> ConversationResult`:
  - Orchestrates replay + scoring in sequence

## 5. Fixtures (`eval/conftest.py`)

- [ ] 5.1 `load_sample_conversations() -> list[dict]`: reads all JSON files from `eval/sample/`
- [ ] 5.2 `build_eval_agent()` fixture: compiles agent graph with real LLM + mock QuoteClient
  (quote calls are mocked with realistic deterministic responses based on lead data)
- [ ] 5.3 `build_eval_judge()` fixture: returns `ChatOpenAI` with structured output via
  `build_judge()`
- [ ] 5.4 `sample_conversations` fixture: returns loaded conversations
- [ ] 5.5 `conversation_result(event_loop, sample_conversations, ...)` parametrized fixture:
  replays and scores a single conversation, yields `ConversationResult`

## 6. Test (`eval/test_eval.py`)

- [ ] 6.1 Single `@pytest.mark.eval` test (`module-level `pytestmark`):
  - Replays all ~30 sample conversations through agent + judge in sequence
  - Scores every turn across all 4 rubric dimensions
  - Calls `build_report()` to compute per-dimension averages and pass rate
  - Calls `write_report()` to persist results as timestamped JSON lines to `eval/results/`
  - Smoke assertions: total conversations match sample count, per-dimension averages in 1–5 range

The test file is intentionally thin — all evaluation logic lives in `judge.py`,
`runner.py`, and `report.py`. The sample itself is the scenario matrix
(qualification, routing, quote handling, objections, PII) annotated via the JSON
metadata, so the judge covers every category without needing separate test files.

## 7. Reporting (`eval/report.py`)

- [ ] 7.1 Create `EvalReport` Pydantic model:
  - `timestamp: str`
  - `total_conversations: int`
  - `total_turns: int`
  - `per_dimension_avg: dict[str, float]` — average score per rubric dimension
  - `pass_rate: float` — fraction of turns with all dimensions ≥ 4
  - `results: list[ConversationResult]`
- [ ] 7.2 Create `build_report(results: list[ConversationResult]) -> EvalReport`:
  - Compute aggregate statistics
  - Print formatted summary to stdout
- [ ] 7.3 Create `write_report(report: EvalReport, path: Path)`:
  - Write JSON lines to `eval/results/{timestamp}.jsonl`
  - One line per `ConversationResult`
- [ ] 7.4 `eval/results/.gitkeep` — tracked empty file; `*.jsonl` in `.gitignore`

## 8. Lint & Format

- [ ] 8.1 Run `ruff check --fix eval/` — zero errors
- [ ] 8.2 Run `ruff format eval/` — no changes
- [ ] 8.3 Run `uv run pytest -m "not eval"` — all fast tests still green
- [ ] 8.4 Run `uv run pytest -m "eval"` — eval tests pass (requires OpenRouter key)