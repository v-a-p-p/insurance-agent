# Mission

## What Is This Project About

An AI agent that handles auto insurance leads end-to-end for **AutoSeguro** (fictional
insurer): WhatsApp conversation → qualification → quote via legacy HTTP API → decision
(resolve or escalate to a human). Built as a technical challenge for the Namastex FDE role.

The agent must deliver a real, working integration against an **unreliable legacy quote
service** (20% failure rate, 10% slow responses) and demonstrate production-grade
resilience, observability, and data-sensitivity practices.

## Challenge Scope

The challenge scope live in `/namastex-fde-challenge/` — this directory is provided as-is and **must not be edited**. All agent code goes in the project root.

## Target Audience

- **Primary**: Namastex engineering team evaluating the challenge.
- **Secondary**: Any engineer onboarding onto the codebase — decisions must be obvious
  from the code and README alone.

## What Success Looks Like

| # | Criterion | Why It Matters |
|---|---|---|
| 1 | **End-to-end correctness** — agent completes the happy path without breaking | Proves the integration works |
| 2 | **Graceful degradation** — `/quote` failures and slowness are handled with retry + backoff, never block the conversation, never invent prices | **The main differentiator** |
| 3 | **Explicit handoff criteria** — the rule for escalating to a human is documented and defensible (refused quote, lead asks for person, 3 consecutive API failures, insufficient data after N qualification attempts) | Transparency in decision-making |
| 4 | **Traceability** — every message and quote carries an ID and status, structured logs are JSON, agent state is persisted via LangGraph checkpoints | Debuggability and audit |
| 5 | **Data sensitivity** — PII patterns (CPF, email, phone, license plate) are detected and handled at the agent level; no sensitive data in logs or LLM context longer than needed | Security posture |
| 6 | **Code quality** — another engineer can read the code and understand every decision without asking | Maintainability |
| 7 | **AI transparency** — all AI tool conversations exported to `ai-logs/`, as required by the challenge | Integrity |

### Decision North Star

When trading off between robustness and simplicity, **choose robustness**. The quote API
is unstable by design — the agent must be resilient by design too. Every failure mode of
the upstream service is expected and handled.