"""The recovery loop — Phase 2 (SPEC.md §5, §7, §8).

``run_batch(seed, mode, baseline)`` runs every event through
triage -> root_cause -> plan -> compliance -> execute -> audit, then aggregates and builds
the leak graph. With ``persist=True`` it resets the DB, reseeds, and writes the pipeline
tables + one ``batch_run`` row.

CLI:
    python -m app.pipeline --seed 7 --mode auto [--baseline]
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from datetime import timedelta

from .batchstats import compute_batch_stats
from .compliance import ComplianceEngine, Decision
from .config import settings
from .diagnose import run_root_cause
from .enums import Action, Actor, Channel, ComplianceDisposition, EventType, Outcome, Stage
from .leakgraph import build_leak_graph
from .models import AuditEntry, BatchRun, Diagnosis, Execution, Plan, ReviewItem
from .outcome import draw_outcome
from .policy import baseline_action, candidate_actions
from .seed import REFERENCE_NOW, generate
from .seed import write as seed_write

_RECOVERABILITY = {
    EventType.payment_failed.value: 0.70,
    EventType.subscription_failed.value: 0.65,
    EventType.checkout_abandoned.value: 0.55,
    EventType.invoice_overdue.value: 0.50,
}


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditLog:
    """Append-only. Deterministic monotonic ids + timestamps (off the reference clock)."""

    def __init__(self) -> None:
        self._rows: list[AuditEntry] = []

    def append(self, event_id: str, stage: Stage, actor: Actor, detail: dict) -> None:
        n = len(self._rows) + 1
        self._rows.append(
            AuditEntry(
                id=f"aud_{n:06d}",
                ts=_iso(REFERENCE_NOW + timedelta(seconds=n)),
                event_id=event_id,
                stage=stage.value,
                actor=actor.value,
                detail=detail,
            )
        )

    @property
    def rows(self) -> list[AuditEntry]:
        return self._rows


def run_triage(event, p75_by_type: dict[str, int]) -> dict:
    rec = _RECOVERABILITY.get(event.type, 0.5)
    attempt = int((event.meta or {}).get("attempt_no", 1))
    rec = max(0.1, rec - 0.06 * (attempt - 1))
    if event.amount >= p75_by_type.get(event.type, 10**12):
        priority = "high"
    elif event.amount < 500:
        priority = "low"
    else:
        priority = "medium"
    return {"expected_loss": event.amount, "recoverability": round(rec, 2), "priority": priority}


def _execute(event, customer, decision: Decision, rng: random.Random) -> tuple[Outcome, int, int]:
    d = decision.disposition
    if d == ComplianceDisposition.passed:
        if decision.action == Action.no_action_stop:
            return Outcome.failed, 0, 0
        return draw_outcome(
            event_type=EventType(event.type),
            amount=event.amount,
            true_cause=_safe_cause(event.true_cause),
            action=decision.action,
            responsiveness=customer.responsiveness,
            rng=rng,
        )
    if d == ComplianceDisposition.deferred:
        return Outcome.deferred, 0, 0
    if d == ComplianceDisposition.awaiting_review:
        return Outcome.awaiting_review, 0, 0
    return Outcome.suppressed, 0, 0


def _safe_cause(value: str):
    from .enums import Cause

    try:
        return Cause(value)
    except ValueError:
        return Cause.undetermined


def _aggregate(events, diagnoses, executions, engine, audit, base_rate: float) -> dict:
    at_risk = sum(e.amount for e in events)
    recovered = sum(x.amount_recovered for x in executions)
    outreach_cost = sum(x.outreach_cost for x in executions)
    rate = recovered / at_risk if at_risk else 0.0

    cause_of = {d.event_id: d.cause for d in diagnoses}
    recovered_of = {x.event_id: x.amount_recovered for x in executions}
    by_cause: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for e in events:
        row = by_cause[cause_of.get(e.id, "undetermined")]
        row[0] += e.amount
        row[1] += recovered_of.get(e.id, 0)

    need = {Stage.triage.value, Stage.root_cause.value, Stage.plan.value, Stage.compliance.value, Stage.execute.value}
    seen: dict[str, set[str]] = defaultdict(set)
    for r in audit.rows:
        seen[r.event_id].add(r.stage)
    full = sum(1 for s in seen.values() if need <= s)

    return {
        "revenue_at_risk": at_risk,
        "revenue_recovered": recovered,
        "recovery_rate": round(rate, 4),
        "baseline_recovery_rate": round(base_rate, 4),
        "outreach_cost": outreach_cost,
        "net_recovery": recovered - outreach_cost,
        "cost_per_rupee_recovered": round(outreach_cost / recovered, 4) if recovered else 0.0,
        "audit_coverage": round(full / len(events), 4) if events else 0.0,
        "recovered_by_cause": [
            {"cause": c, "at_risk": v[0], "recovered": v[1]}
            for c, v in sorted(by_cause.items(), key=lambda kv: -kv[1][0])
        ],
        "compliance": dict(engine.counters),
    }


def run_batch(seed: int = 7, mode: str = "auto", baseline: bool = False, persist: bool = True) -> dict:
    customers, events = generate(seed)
    by_id = {c.id: c for c in customers}
    if persist:
        seed_write(customers, events)  # resets DB, inserts customer + revenue_event

    # Fair comparison: the naive baseline runs through the SAME compliance engine, so both
    # withhold action on disputed / promise-to-pay accounts. Only the routing differs.
    if baseline:
        baseline_rate = None  # a baseline run reports itself
    else:
        b = run_batch(seed, mode="auto", baseline=True, persist=False)
        baseline_rate = b["aggregates"]["recovery_rate"]

    stats = compute_batch_stats(events, customers)
    engine = ComplianceEngine(customers, now=REFERENCE_NOW)
    audit = AuditLog()
    diagnoses: list[Diagnosis] = []
    plans: list[Plan] = []
    executions: list[Execution] = []
    reviews: list[ReviewItem] = []

    for e in events:
        cust = by_id[e.customer_id]
        rng = random.Random((seed << 20) ^ int(e.id.split("_")[1]))

        tri = run_triage(e, stats.amount_p75_by_type)
        audit.append(e.id, Stage.triage, Actor.agent, tri)

        cause, conf, evidence = run_root_cause(e, cust, stats)
        diagnoses.append(Diagnosis(event_id=e.id, cause=cause, confidence=conf, evidence=evidence))
        audit.append(e.id, Stage.root_cause, Actor.agent, {"cause": cause, "confidence": conf, "evidence": evidence})

        if baseline:
            candidates = [baseline_action(e.type)]
        else:
            candidates = candidate_actions(e.type, cause)
        audit.append(e.id, Stage.plan, Actor.agent, {"primary": candidates[0].value, "ladder": [a.value for a in candidates]})

        decision = engine.resolve(e, cust, cause, candidates, mode)
        plans.append(
            Plan(
                event_id=e.id,
                action=decision.action.value,
                channel=decision.channel.value,
                blocked_by=decision.rule_id.value if decision.rule_id else None,
            )
        )
        audit.append(
            e.id, Stage.compliance, Actor.compliance,
            {"disposition": decision.disposition.value, "rule": decision.rule_id.value if decision.rule_id else None, **decision.detail},
        )

        outcome, recovered, cost = _execute(e, cust, decision, rng)
        executions.append(
            Execution(
                event_id=e.id,
                action=decision.action.value,
                channel=decision.channel.value,
                attempted_at=_iso(REFERENCE_NOW + timedelta(seconds=len(executions) + 1)),
                outcome=outcome.value,
                amount_recovered=recovered,
                outreach_cost=cost,
            )
        )
        audit.append(e.id, Stage.execute, Actor.agent, {"outcome": outcome.value, "amount_recovered": recovered, "outreach_cost": cost})

        if decision.disposition == ComplianceDisposition.awaiting_review:
            reviews.append(ReviewItem(event_id=e.id, action=decision.action.value, status="pending"))
        elif decision.disposition == ComplianceDisposition.passed:
            engine.counters["auto_executed"] += 1
            if decision.channel != Channel.none:
                engine.record_outreach(cust.id, decision.action)

    at_risk = sum(e.amount for e in events) or 1
    self_rate = round(sum(x.amount_recovered for x in executions) / at_risk, 4)
    aggregates = _aggregate(
        events, diagnoses, executions, engine, audit,
        base_rate=self_rate if baseline_rate is None else baseline_rate,
    )
    graph = build_leak_graph(events, diagnoses, executions, customers)
    run_info = {"seed": seed, "mode": mode, "baseline": baseline, "ran_at": _iso(REFERENCE_NOW), "event_count": len(events)}

    if persist:
        _persist(diagnoses, plans, executions, reviews, audit.rows, run_info, aggregates, graph, engine.items)

    return {"run": run_info, "aggregates": aggregates, "leak_graph": graph, "compliance_items": engine.items}


def _persist(diagnoses, plans, executions, reviews, audit_rows, run_info, aggregates, graph, compliance_items) -> None:
    from sqlmodel import Session, delete

    from .db import ENGINE

    with Session(ENGINE) as s:
        for model in (AuditEntry, ReviewItem, Execution, Plan, Diagnosis, BatchRun):
            s.exec(delete(model))
        s.add_all(diagnoses)
        s.add_all(plans)
        s.add_all(executions)
        s.add_all(reviews)
        s.add_all(audit_rows)
        s.add(
            BatchRun(
                seed=run_info["seed"],
                mode=run_info["mode"],
                baseline=run_info["baseline"],
                ran_at=run_info["ran_at"],
                event_count=run_info["event_count"],
                aggregates={**aggregates, "compliance_items": compliance_items},
                leak_graph=graph,
            )
        )
        s.commit()


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def _format(result: dict, seed: int) -> str:
    a = result["aggregates"]
    c = a["compliance"]
    L: list[str] = ["", f"  seed={seed}  mode={result['run']['mode']}  baseline={result['run']['baseline']}", ""]
    L.append(f"  revenue at risk ....... Rs {a['revenue_at_risk']:>11,}")
    L.append(f"  revenue recovered ..... Rs {a['revenue_recovered']:>11,}   {a['recovery_rate'] * 100:5.1f}%")
    L.append(f"  naive baseline ........ {a['baseline_recovery_rate'] * 100:5.1f}%   (delta {(a['recovery_rate'] - a['baseline_recovery_rate']) * 100:+.1f} pts)")
    L.append(f"  outreach cost ......... Rs {a['outreach_cost']:>11,}")
    L.append(f"  net recovery .......... Rs {a['net_recovery']:>11,}")
    L.append(f"  audit coverage ....... {a['audit_coverage'] * 100:.0f}%")
    L.append("")
    L.append("  compliance:")
    for k in ("auto_executed", "deferred", "suppressed", "stopped", "escalated", "awaiting_review"):
        L.append(f"    {k:<16} {c[k]:>4}")
    L.append("")
    L.append("  recovered by cause (top 6):")
    for row in a["recovered_by_cause"][:6]:
        rr = 100 * row["recovered"] / row["at_risk"] if row["at_risk"] else 0
        L.append(f"    {row['cause']:<34} Rs {row['recovered']:>10,} / {row['at_risk']:>10,}   {rr:4.0f}%")
    L.append("")
    L.append("  leak graph failure -> loss:")
    for e in result["leak_graph"]["edges"]:
        if e["target"] == "loss:total":
            L.append(f"    {e['source'].split(':', 1)[1]:<30} Rs {e['rupees']:>10,}  {e['label']}")
    L.append("")
    return "\n".join(L)


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Run one Revenue Sherlock batch.")
    ap.add_argument("--seed", type=int, default=settings.demo_seed)
    ap.add_argument("--mode", choices=["auto", "review"], default="auto")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--no-persist", action="store_true", help="skip DB writes")
    args = ap.parse_args()

    result = run_batch(args.seed, args.mode, args.baseline, persist=not args.no_persist)
    print(_format(result, args.seed))

    # quick attribution accuracy vs the hidden ground truth
    customers, events = generate(args.seed)
    by_id = {c.id: c for c in customers}
    stats = compute_batch_stats(events, customers)
    hit = sum(1 for e in events if run_root_cause(e, by_id[e.customer_id], stats)[0] == e.true_cause)
    print(f"  diagnosis accuracy vs true_cause: {hit}/{len(events)}  ({100 * hit / len(events):.1f}%)\n")


if __name__ == "__main__":
    _cli()
