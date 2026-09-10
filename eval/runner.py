from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from eval.judge import RubricScore, judge_turn


class TurnResult(BaseModel):
    """Result of a single conversation turn: lead message, agent reply, judge scores, and graph nodes visited."""

    turn_index: int
    lead_message: str
    agent_reply: str
    rubric: RubricScore | None = None
    graph_path: list[str]


class ConversationResult(BaseModel):
    """Full replay result for one conversation: ID, annotations, per-turn results, and overall rubric."""

    conversation_id: str
    annotations: dict
    turns: list[TurnResult]
    overall_rubric: RubricScore | None = None


def _truncate(text: str, max_len: int = 100) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _print_header(
    progress: str, conversation_id: str, outcome: str, total_turns: int
) -> None:
    label = f"  {progress} {conversation_id}" if progress else f"  {conversation_id}"
    print(f"\n{'=' * 60}")
    print(f"  {label} ({outcome}, {total_turns} turnos)")
    print(f"{'=' * 60}")


def _print_turn(
    idx: int, total: int, lead_msg: str, agent_reply: str, graph_path: list[str]
) -> None:
    print(f"\n  Turno {idx + 1}/{total} — graph: {', '.join(graph_path)}")
    print(f"  {'─' * 56}")
    print(f"  [lead]  {_truncate(lead_msg)}")
    print(f"  [agent] {_truncate(agent_reply)}")


def _print_turn_scores(rubric: RubricScore) -> None:
    print(
        f"  {'─' * 56}\n"
        f"    rel={rubric.relevancia.score} "
        f"tom={rubric.tom.score} "
        f"prec={rubric.precisao_factual.score} "
        f"pii={rubric.seguranca_pii.score}"
    )


def _print_conversation_avg(
    avg_rel: float, avg_tom: float, avg_prec: float, avg_pii: float
) -> None:
    print(
        f"  {'─' * 56}\n"
        f"    Media: rel={avg_rel:.1f} tom={avg_tom:.1f} prec={avg_prec:.1f} pii={avg_pii:.1f}"
    )


async def _astream_graph_path(
    agent: CompiledStateGraph, input_state: dict, config: RunnableConfig
) -> tuple[str, list[str]]:
    """Stream one agent invocation, collecting the last AIMessage content and ordered node names visited."""
    path: list[str] = []
    last_message = ""

    async for chunk in agent.astream(input_state, config, stream_mode="updates"):
        for node_name in chunk:
            if node_name not in path:
                path.append(node_name)
            node_output = chunk[node_name]
            if isinstance(node_output, dict) and "messages" in node_output:
                for msg in node_output["messages"]:
                    if isinstance(msg, AIMessage):
                        last_message = msg.content

    return last_message, path


async def replay_conversation(
    agent: CompiledStateGraph,
    conversation: dict,
    verbose: bool = False,
    progress: str = "",
) -> ConversationResult:
    """Replay all lead messages through the agent graph sequentially, capturing replies and graph paths."""
    conversation_id = conversation["conversation_id"]
    annotations = conversation.get("annotations", {})
    messages = conversation["messages"]

    lead_messages = [m for m in messages if m["sender_role"] == "lead"]
    total_turns = len(lead_messages)

    config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}

    if verbose:
        outcome = conversation.get("outcome", "?")
        _print_header(progress, conversation_id, outcome, total_turns)

    turns: list[TurnResult] = []
    for idx, msg in enumerate(lead_messages):
        input_state = {"messages": [HumanMessage(content=msg["message_body"])]}
        reply, path = await _astream_graph_path(agent, input_state, config)

        if verbose:
            _print_turn(idx, total_turns, msg["message_body"], reply, path)

        turns.append(
            TurnResult(
                turn_index=idx,
                lead_message=msg["message_body"],
                agent_reply=reply or "",
                graph_path=path,
            )
        )

    return ConversationResult(
        conversation_id=conversation_id,
        annotations=annotations,
        turns=turns,
    )


async def score_conversation(
    judge: Any,
    result: ConversationResult,
    verbose: bool = False,
) -> ConversationResult:
    """Score every turn using the judge LLM and compute an overall rubric from per-dimension averages."""
    context = {
        "outcome": result.annotations.get("expected_outcome", ""),
        "lead_opening_style": result.annotations.get("lead_opening_style", ""),
        "plan_tier": result.annotations.get("plan_tier", ""),
    }

    scored_turns: list[TurnResult] = []
    for turn in result.turns:
        rubric = await judge_turn(
            judge=judge,
            lead_msg=turn.lead_message,
            agent_reply=turn.agent_reply,
            context=context,
        )
        scored_turns.append(
            TurnResult(
                turn_index=turn.turn_index,
                lead_message=turn.lead_message,
                agent_reply=turn.agent_reply,
                rubric=rubric,
                graph_path=turn.graph_path,
            )
        )

        if verbose:
            _print_turn_scores(rubric)

    overall_scores: list[RubricScore] = [
        t.rubric for t in scored_turns if t.rubric is not None
    ]
    overall_rubric = None
    if overall_scores:
        avg_rel = sum(s.relevancia.score for s in overall_scores) / len(overall_scores)
        avg_tom = sum(s.tom.score for s in overall_scores) / len(overall_scores)
        avg_prec = sum(s.precisao_factual.score for s in overall_scores) / len(
            overall_scores
        )
        avg_pii = sum(s.seguranca_pii.score for s in overall_scores) / len(
            overall_scores
        )

        from eval.judge import RubricDimension

        overall_rubric = RubricScore(
            relevancia=RubricDimension(
                score=round(avg_rel), justificativa="media das notas dos turnos"
            ),
            tom=RubricDimension(
                score=round(avg_tom), justificativa="media das notas dos turnos"
            ),
            precisao_factual=RubricDimension(
                score=round(avg_prec), justificativa="media das notas dos turnos"
            ),
            seguranca_pii=RubricDimension(
                score=round(avg_pii), justificativa="media das notas dos turnos"
            ),
        )

        if verbose:
            _print_conversation_avg(avg_rel, avg_tom, avg_prec, avg_pii)

    return ConversationResult(
        conversation_id=result.conversation_id,
        annotations=result.annotations,
        turns=scored_turns,
        overall_rubric=overall_rubric,
    )


async def run_replay(
    agent: CompiledStateGraph,
    judge: Any,
    conversation: dict,
    verbose: bool = False,
    progress: str = "",
) -> ConversationResult:
    """Replay all lead messages through the agent, scoring each turn immediately after."""
    conversation_id = conversation["conversation_id"]
    annotations = conversation.get("annotations", {})
    messages = conversation["messages"]

    lead_messages = [m for m in messages if m["sender_role"] == "lead"]
    total_turns = len(lead_messages)

    config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}

    if verbose:
        outcome = conversation.get("outcome", "?")
        _print_header(progress, conversation_id, outcome, total_turns)

    context = {
        "outcome": annotations.get("expected_outcome", ""),
        "lead_opening_style": annotations.get("lead_opening_style", ""),
        "plan_tier": annotations.get("plan_tier", ""),
    }

    turns: list[TurnResult] = []
    all_rel, all_tom, all_prec, all_pii = 0, 0, 0, 0
    scored_count = 0

    for idx, msg in enumerate(lead_messages):
        reply, path = await _astream_graph_path(
            agent,
            {"messages": [HumanMessage(content=msg["message_body"])]},
            config,
        )

        if verbose:
            _print_turn(idx, total_turns, msg["message_body"], reply, path)

        rubric = await judge_turn(
            judge=judge,
            lead_msg=msg["message_body"],
            agent_reply=reply or "",
            context=context,
        )

        if verbose:
            _print_turn_scores(rubric)

        turns.append(
            TurnResult(
                turn_index=idx,
                lead_message=msg["message_body"],
                agent_reply=reply or "",
                rubric=rubric,
                graph_path=path,
            )
        )

        all_rel += rubric.relevancia.score
        all_tom += rubric.tom.score
        all_prec += rubric.precisao_factual.score
        all_pii += rubric.seguranca_pii.score
        scored_count += 1

    overall_rubric = None
    if scored_count:
        avg_rel = all_rel / scored_count
        avg_tom = all_tom / scored_count
        avg_prec = all_prec / scored_count
        avg_pii = all_pii / scored_count

        from eval.judge import RubricDimension

        overall_rubric = RubricScore(
            relevancia=RubricDimension(
                score=round(avg_rel), justificativa="media das notas dos turnos"
            ),
            tom=RubricDimension(
                score=round(avg_tom), justificativa="media das notas dos turnos"
            ),
            precisao_factual=RubricDimension(
                score=round(avg_prec), justificativa="media das notas dos turnos"
            ),
            seguranca_pii=RubricDimension(
                score=round(avg_pii), justificativa="media das notas dos turnos"
            ),
        )

        if verbose:
            _print_conversation_avg(avg_rel, avg_tom, avg_prec, avg_pii)

    return ConversationResult(
        conversation_id=conversation_id,
        annotations=annotations,
        turns=turns,
        overall_rubric=overall_rubric,
    )
