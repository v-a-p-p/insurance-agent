from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval.report import build_report, write_report
from eval.runner import run_replay

pytestmark = pytest.mark.eval

RESULTS_DIR = Path("eval/results")


@pytest.mark.asyncio
async def test_eval_full_run(eval_agent, eval_judge, sample_conversations):
    total = len(sample_conversations)
    results = []
    for i, conv in enumerate(sample_conversations):
        progress = f"[{i + 1}/{total}]"
        result = await run_replay(
            eval_agent, eval_judge, conv, verbose=True, progress=progress
        )
        results.append(result)

    report = build_report(results)
    assert report.total_conversations == total

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    write_report(report, RESULTS_DIR / f"{timestamp}.jsonl")

    assert report.total_turns > 0
    for dim, avg in report.per_dimension_avg.items():
        assert 1.0 <= avg <= 5.0, f"{dim} avg {avg} out of range"
