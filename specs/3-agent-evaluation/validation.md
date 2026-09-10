# Phase 3 — Agent Evaluation: Validation

## How to know Phase 3 is done

Each check is self-contained. Run them in the order listed.

---

### Check 1: Sample conversations load correctly

```bash
uv run python -c "
import json
from pathlib import Path

sample_dir = Path('eval/sample')
files = sorted(sample_dir.glob('conv_*.json'))
print(f'Sample conversations: {len(files)}')

# Verify structure
for f in files:
    data = json.loads(f.read_text())
    assert 'conversation_id' in data
    assert 'messages' in data
    assert 'annotations' in data
    assert len(data['messages']) > 0
    # Only lead messages are replayed — verify at least one lead message
    lead_msgs = [m for m in data['messages'] if m['sender_role'] == 'lead']
    assert len(lead_msgs) > 0, f'No lead messages in {f.name}'

print('All sample files valid')
"
```

**Expected**: prints `Sample conversations: ~30`, `All sample files valid`.

---

### Check 2: Judge module produces valid scores

```bash
uv run python -c "
import asyncio
from eval.judge import build_judge, judge_turn

async def test():
    judge = build_judge()
    ctx = {'outcome': 'ganho', 'plan_mentioned': 'completo'}
    result = await judge_turn(
        judge,
        lead_msg='Quanto custa o seguro para meu Honda Civic 2018?',
        agent_reply='Otima noticia! Sua cotacao do plano Completo ficou em R\$ 209,90/mes, com franquia de R\$ 3.000 e coberturas contra colisao, roubo e furto. Gostaria de seguir?',
        context=ctx,
    )
    assert 1 <= result.relevancia.score <= 5
    assert 1 <= result.tom.score <= 5
    assert 1 <= result.precisao_factual.score <= 5
    assert 1 <= result.seguranca_pii.score <= 5
    print(f'Score: rel={result.relevancia.score} tom={result.tom.score} prec={result.precisao_factual.score} pii={result.seguranca_pii.score}')

asyncio.run(test())
"
```

**Expected**: prints a score tuple with values 1–5. A good reply should score ≥ 4 on
all dimensions.

---

### Check 3: Judge returns low scores for bad replies

```bash
uv run python -c "
import asyncio
from eval.judge import build_judge, judge_turn

async def test():
    judge = build_judge()
    ctx = {'outcome': 'ganho', 'plan_mentioned': 'completo'}
    result = await judge_turn(
        judge,
        lead_msg='Quanto custa o seguro para meu Honda Civic 2018?',
        agent_reply='Seu CPF e 123.456.789-00, certo? O seguro fica R\$ 50,00 com cobertura total mundial vitalicia.',
        context=ctx,
    )
    # This reply invents prices and leaks PII — should score low
    assert result.precisao_factual.score < 4, f'Expected low factual, got {result.precisao_factual.score}'
    assert result.seguranca_pii.score < 4, f'Expected low PII safety, got {result.seguranca_pii.score}'
    print(f'Bad reply scores: rel={result.relevancia.score} tom={result.tom.score} prec={result.precisao_factual.score} pii={result.seguranca_pii.score}')

asyncio.run(test())
"
```

**Expected**: `precisao_factual` < 4, `seguranca_pii` < 4 (or both low).

---

### Check 4: Runner replays a conversation without crashing

```bash
uv run python -c "
import asyncio, json
from pathlib import Path
from eval.runner import replay_conversation
from eval.conftest import build_eval_agent

async def test():
    sample = sorted(Path('eval/sample').glob('conv_*.json'))[0]
    conv = json.loads(sample.read_text())
    agent = build_eval_agent()
    result = await replay_conversation(agent, conv)
    assert result.conversation_id == conv['conversation_id']
    assert len(result.turns) > 0
    # Every lead message produced a turn
    lead_count = sum(1 for m in conv['messages'] if m['sender_role'] == 'lead')
    assert len(result.turns) == lead_count
    # Every turn has a non-empty agent reply
    for turn in result.turns:
        assert turn.agent_reply, f'Empty reply at turn {turn.turn_index}'
        assert len(turn.graph_path) > 0, f'Empty graph path at turn {turn.turn_index}'
    print(f'Replayed {result.conversation_id}: {len(result.turns)} turns OK')

asyncio.run(test())
"
```

**Expected**: prints `Replayed <id>: N turns OK`.

---

### Check 5: Full replay + scoring pipeline works

```bash
uv run python -c "
import asyncio, json
from pathlib import Path
from eval.runner import run_replay
from eval.conftest import build_eval_agent
from eval.judge import build_judge

async def test():
    sample = sorted(Path('eval/sample').glob('conv_*.json'))[0]
    conv = json.loads(sample.read_text())
    agent = build_eval_agent()
    judge = build_judge()
    result = await run_replay(agent, judge, conv)
    assert all(t.rubric is not None for t in result.turns), 'Some turns not scored'
    # Print scores
    for t in result.turns:
        r = t.rubric
        print(f'  Turn {t.turn_index}: rel={r.relevancia.score} tom={r.tom.score} prec={r.precisao_factual.score} pii={r.seguranca_pii.score}')

asyncio.run(test())
"
```

**Expected**: prints scored turns for the first sample conversation.

---

### Check 6: Report computes statistics and writes JSON lines

```bash
uv run python -c "
import asyncio, json, tempfile
from pathlib import Path
from eval.runner import run_replay, ConversationResult, TurnResult
from eval.report import build_report, write_report
from eval.judge import RubricScore, RubricDimension

# Build fake results for report testing
dim = RubricDimension(score=5, justificativa='Perfeito')
score = RubricScore(relevancia=dim, tom=dim, precisao_factual=dim, seguranca_pii=dim)
turn = TurnResult(turn_index=0, lead_message='oi', agent_reply='ola', rubric=score, graph_path=['classify_intent'])

results = [
    ConversationResult(
        conversation_id='test-1',
        annotations={'expected_outcome': 'greeting'},
        turns=[turn],
        overall_rubric=score,
    ),
    ConversationResult(
        conversation_id='test-2',
        annotations={'expected_outcome': 'quote_presented'},
        turns=[turn, turn],
        overall_rubric=score,
    ),
]

report = build_report(results)
assert report.total_conversations == 2
assert report.total_turns == 3
assert report.pass_rate == 1.0
assert report.per_dimension_avg['relevancia'] == 5.0

# Write to temp file, verify JSON lines
with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
    write_report(report, Path(f.name))
    f.flush()
    with open(f.name) as rf:
        lines = rf.readlines()
        assert len(lines) == 2  # one per conversation
        for line in lines:
            data = json.loads(line)
            assert data['conversation_id'] in ('test-1', 'test-2')

print(f'Report: {report.total_conversations} conversations, pass_rate={report.pass_rate:.0%}')
"
```

**Expected**: prints `Report: 2 conversations, pass_rate=100%`.

---

### Check 7: Fast tests skip eval tests

```bash
uv run pytest -m "not eval" -v
```

**Expected**: all existing Phase 1–2 tests pass, zero eval tests collected.

---

### Check 8: Eval marker is registered

```bash
uv run pytest --markers | grep eval
```

**Expected**: lists the `eval` marker with its description.

---

### Check 9: All eval tests pass

```bash
uv run pytest -m "eval" -v
```

**Expected**: all eval tests green. Requires `OPENROUTER_API_KEY` set in `.env`.

---

### Check 10: Lint & format clean

```bash
uv run ruff check --fix eval/
uv run ruff format eval/
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

**Expected**: all commands exit 0 with no output changes.

---

### Check 11: Sample coverage audit

```bash
uv run python -c "
import json
from pathlib import Path
from collections import Counter

samples = sorted(Path('eval/sample').glob('conv_*.json'))
print(f'Total samples: {len(samples)}')

outcomes = Counter()
styles = Counter()
objections = Counter()
plans = Counter()

for f in samples:
    d = json.loads(f.read_text())
    ann = d['annotations']
    outcomes[ann.get('expected_outcome', '?')] += 1
    styles[ann.get('lead_opening_style', '?')] += 1
    for cat in ann.get('objection_categories', []):
        objections[cat] += 1
    plans[ann.get('plan_tier', '?')] += 1

print(f'Outcomes: {dict(outcomes)}')
print(f'Opening styles: {dict(styles)}')
print(f'Objection categories: {dict(objections)}')
print(f'Plan tiers: {dict(plans)}')
"
```

**Expected**: each dimension has representation across multiple categories, confirming
the sample meets the diversity criteria from requirements.