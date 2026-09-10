from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from eval.runner import ConversationResult


class EvalReport(BaseModel):
    """Aggregate evaluation report: timestamp, totals, per-dimension averages, pass rate, and full results."""

    timestamp: str
    total_conversations: int
    total_turns: int
    per_dimension_avg: dict[str, float]
    pass_rate: float
    results: list[ConversationResult]


def build_report(results: list[ConversationResult]) -> EvalReport:
    """Compute aggregate statistics from conversation results, print a formatted summary, and return an EvalReport."""
    total_turns = sum(len(r.turns) for r in results)

    all_scores: dict[str, list[int]] = {
        "relevancia": [],
        "tom": [],
        "precisao_factual": [],
        "seguranca_pii": [],
    }

    passing_turns = 0
    total_scored_turns = 0

    for conv in results:
        for turn in conv.turns:
            if turn.rubric is None:
                continue
            total_scored_turns += 1
            all_scores["relevancia"].append(turn.rubric.relevancia.score)
            all_scores["tom"].append(turn.rubric.tom.score)
            all_scores["precisao_factual"].append(turn.rubric.precisao_factual.score)
            all_scores["seguranca_pii"].append(turn.rubric.seguranca_pii.score)
            if turn.rubric.all_passing():
                passing_turns += 1

    per_dimension_avg = {
        dim: sum(scores) / len(scores) if scores else 0.0
        for dim, scores in all_scores.items()
    }

    pass_rate = passing_turns / total_scored_turns if total_scored_turns > 0 else 0.0

    report = EvalReport(
        timestamp=datetime.now(UTC).isoformat(),
        total_conversations=len(results),
        total_turns=total_turns,
        per_dimension_avg=per_dimension_avg,
        pass_rate=pass_rate,
        results=results,
    )

    _print_summary(report)
    return report


def _print_summary(report: EvalReport) -> None:
    """Print a formatted table of aggregate evaluation statistics to stdout."""
    print(f"\n{'=' * 60}")
    print("  AVALIACAO DO AGENTE — Relatorio Final")
    print(f"{'=' * 60}")
    print(f"  Timestamp:         {report.timestamp}")
    print(f"  Conversas:          {report.total_conversations}")
    print(f"  Turnos:             {report.total_turns}")
    print(f"  Pass rate:          {report.pass_rate:.1%}")
    print(f"  Media Relevancia:   {report.per_dimension_avg.get('relevancia', 0):.2f}")
    print(f"  Media Tom:          {report.per_dimension_avg.get('tom', 0):.2f}")
    print(
        f"  Media Prec. Factual:{report.per_dimension_avg.get('precisao_factual', 0):.2f}"
    )
    print(
        f"  Media Seg. PII:     {report.per_dimension_avg.get('seguranca_pii', 0):.2f}"
    )
    print(f"{'=' * 60}\n")


def write_report(report: EvalReport, path: Path) -> None:
    """Write an EvalReport to disk as JSON lines (one ConversationResult per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.writelines(result.model_dump_json() + "\n" for result in report.results)
