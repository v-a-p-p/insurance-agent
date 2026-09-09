# AGENTS.md

## Rules

Load `.agents/rules/fastapi-best-practices.md` when writing any FastAPI code
(routes, schemas, dependencies, middleware). Covers async patterns, Pydantic v2 conventions, Annotated dependencies, httpx testing, and common anti-patterns.

Do not edit the `[tool.uv]` section in `pyproject.toml`.

When adding, removing, or modifying Python dependencies, always use `uv add`, `uv remove`, or `uv add --group dev` instead of editing `pyproject.toml` manually. This ensures `[tool.uv]` settings (e.g., `add-bounds = "exact"`) are applied automatically.

When planning or building, never read or write the `.env` file directly. If any question arises about `.env` values or changes, ask the user instead.

## Skills

Load skills **progressively** — only when planning or working on the relevant layer. `.agents/skills/ecosystem-primer` is the entry point for **agent-building work only** (LangChain / LangGraph / Deep Agents). For FastAPI work, load the `.agents/skills/fastapi` directly. Cross-layer tasks (e.g., an SSE endpoint streaming a LangGraph agent) load both.
