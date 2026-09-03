"""Phase 1 sanity analysis — no DB, regenerates the batch in memory.

Confirms the two properties the demo depends on:
  * determinism — same seed => identical rows (checked in tests)
  * diagnosis-routed recovery clearly beats a naive baseline (SPEC §3.5)

The ``oracle`` policy here is just ``argmax`` over the affinity matrix — it is NOT the real
planner (that's Phase 2, with compliance and stopping rules). It only exists to prove the
data has a recoverable signal at all.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable

from .enums import Action, Cause, EventType
from .models import Customer, RevenueEvent
from .outcome import best_action, draw_outcome
from .seed import generate

BASELINE_BY_TYPE: dict[EventType, Action] = {
    EventType.payment_failed: Action.smart_retry,
    EventType.subscription_failed: Action.smart_retry,
    EventType.checkout_abandoned: Action.payment_link_nudge,
    EventType.invoice_overdue: Action.dunning_email,
}


def _oracle_action(e: RevenueEvent) -> Action:
    return best_action(Cause(e.true_cause))


def _baseline_action(e: RevenueEvent) -> Action:
    return BASELINE_BY_TYPE[EventType(e.type)]


def _simulate(
    events: list[RevenueEvent],
    by_id: dict[str, Customer],
    action_fn: Callable[[RevenueEvent], Action],
    seed: int,
) -> dict:
    rng = random.Random(seed ^ 0x5EED)
    at_risk = recovered = 0
    for e in events:
        at_risk += e.amount
        _, amt, _ = draw_outcome(
            event_type=EventType(e.type),
            amount=e.amount,
            true_cause=Cause(e.true_cause),
            action=action_fn(e),
            responsiveness=by_id[e.customer_id].responsiveness,
            rng=rng,
        )
        recovered += amt
    return {"at_risk": at_risk, "recovered": recovered, "rate": recovered / at_risk if at_risk else 0.0}


def summarize(seed: int) -> dict:
    customers, events = generate(seed)
    by_id = {c.id: c for c in customers}
    return {
        "seed": seed,
        "customers": len(customers),
        "events": len(events),
        "at_risk": sum(e.amount for e in events),
        "cause_hist": dict(Counter(e.true_cause for e in events).most_common()),
        "type_hist": dict(Counter(e.type for e in events).most_common()),
        "oracle": _simulate(events, by_id, _oracle_action, seed),
        "baseline": _simulate(events, by_id, _baseline_action, seed),
    }


def format_report(s: dict) -> str:
    lines = [
        "",
        f"  seed .............. {s['seed']}",
        f"  customers ........ {s['customers']}",
        f"  events ........... {s['events']}",
        f"  revenue at risk .. Rs {s['at_risk']:,}",
        "",
        "  cause mix:",
    ]
    for cause, n in s["cause_hist"].items():
        lines.append(f"    {cause:<34} {n:>3}")
    o, b = s["oracle"], s["baseline"]
    delta = o["rate"] - b["rate"]
    lines += [
        "",
        f"  oracle (best action / cause) .. Rs {o['recovered']:>10,}   {o['rate'] * 100:5.1f}%",
        f"  baseline (naive by type) ...... Rs {b['recovered']:>10,}   {b['rate'] * 100:5.1f}%",
        f"  delta ......................... {delta * 100:+5.1f} pts",
        "",
        f"  CHECK oracle beats baseline by >10 pts: {'PASS' if delta > 0.10 else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)
