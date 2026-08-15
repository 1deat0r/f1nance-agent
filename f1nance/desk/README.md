# F1NANCE Desk — the multi-agent layer

The Phase-5 counterpart to `f1nance/data`, `f1nance/portfolio`,
`f1nance/quant`, and `f1nance/execution`. Where those layers are the
*capabilities* (data, portfolio, quant, execution), this layer is the
*coordination*: one harness, five specialists (PM, trader, quant, banker,
CFO) over the six capability domains, and a single verdict.

Hermes-independent by design: standard library only (`dataclasses`, `typing`,
`json`) — no numpy, no pandas, no Hermes. Runs on any Python 3.9+.

## The idea

A task enters the desk as a `Brief`, is routed to the seats that own it, each
seat returns a `Finding` (thesis + stance + confidence + loss case +
falsification), and the coordinator folds them into a `Verdict` where
consensus and dissent are surfaced and **every loss case survives
aggregation**. The guardrails are structural here: a finding without a loss
case or with a confidence outside `[0, 1]` is an error, not a data point.

The desk does **not** know how a seat's judgment is produced. That is the
`executor` — a single injectable callable `(Seat, Brief) -> Finding`. In tests
and the offline CLI it is scripted; in a live runtime it is a model call or a
delegated subagent. The coordination logic is identical either way, which is
what keeps the body portable toward Phase 6.

## Modules

| Module | What it does |
|---|---|
| `seats` | The five-seat roster (each mapped to its domain, roles, engines, routing keywords) and deterministic routing |
| `brief` | The task/output models — `Brief`, `Finding`, `Verdict` — with structural validation, and the `aggregate` fold |
| `desk` | The `Desk` coordinator (route → dispatch → validate → aggregate) plus the `scripted_executor` for offline runs |

## Use

As a library:

```python
from f1nance.desk import Desk, Brief, scripted_executor

brief = Brief("trim the concentrated AAPL position", risk_capacity="moderate")
findings = {
    "pm": {"thesis": "breaches the 20% cap; trim to 15%", "stance": "bearish",
           "confidence": 0.7, "loss_case": "AAPL keeps outperforming; ~-5%",
           "falsify": "concentration < 20% without action"},
    "trader": {"thesis": "liquidity ample; spread ~5bps", "stance": "neutral",
               "confidence": 0.5, "loss_case": "sell into weakness; >20bps",
               "falsify": "realized spread > 20bps"},
}

verdict = Desk().run(brief, scripted_executor(findings))
verdict.stance      # "mixed" (bearish vs neutral tie)
verdict.confidence  # 0.6
verdict.dissent     # ()
verdict.loss_cases  # {"pm": "...", "trader": "..."} — nothing dropped
```

Swap `scripted_executor` for a real executor to go live:

```python
def model_executor(seat, brief):
    ...  # call the seat's model / delegated subagent, return a Finding
    return Finding(seat.name, thesis, stance, confidence, loss_case, falsify)

verdict = Desk().run(brief, model_executor)
```

From the CLI (all JSON on stdout):

```bash
f1nance/.venv/bin/python -m f1nance.desk seats
f1nance/.venv/bin/python -m f1nance.desk route spec.json
f1nance/.venv/bin/python -m f1nance.desk run spec.json
```

`run` does not call a model: it scripts the executor from a `findings` map in
the spec, so the real route → dispatch → validate → aggregate path runs
deterministically.

## Conventions (trust the trail, not the assumption)

- **Routing is deterministic.** `Brief.seats` (explicit) selects exactly those
  seats; otherwise the objective is matched against each seat's keywords. An
  objective that matches nothing raises — the desk refuses to convene the
  wrong seats on a guess.
- **Confidence is numeric** (`0.0`–`1.0`), canonical; the CLI accepts
  `high`/`medium`/`low` as `0.8`/`0.5`/`0.2`.
- **Risk before return is structural.** A `Finding` without a `loss_case` or a
  `falsify` condition, or with a bad `stance`/`confidence`, raises. The
  `Verdict` carries every seat's loss case and falsification — aggregation
  never drops one.
- **Dissent is surfaced, not averaged away.** `stance` is the plurality
  stance (or `"mixed"` on a tie); `dissent` lists the seats that disagree;
  `agreement` is the largest bloc as a fraction of seats seated.
- **`run` with a scripted executor raises if a seated seat has no finding** —
  the desk will not aggregate a verdict from a silent specialist. Findings
  for seats that are *not* seated are ignored.

## What it deliberately does not do

- **No model calls.** The executor is injected; the desk only coordinates.
  The offline CLI is scripted on purpose.
- **No real subagent spawning.** In the Hermes bootstrap, "spawn a specialist"
  is one executor implementation (a `delegate_task`); here it is one callable.
  The seam is the point — the coordination logic is Hermes-free.
- **No suitability reasoning.** `horizon` and `risk_capacity` are carried on
  the `Brief` to the executor/umbrella; the deterministic coordinator does
  not pretend to reason over them offline.

## Test

```bash
f1nance/.venv/bin/python -m unittest discover -s f1nance/tests -v
```

Offline; no network, no model, no Hermes.
