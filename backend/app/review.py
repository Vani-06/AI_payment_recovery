"""Review Mode decisions — Phase 3.

Approving a queued action executes it now (deterministic per-event RNG, same as the
pipeline), rewrites the execution row, appends a ``human`` audit entry, and refreshes the
money fields on the stored aggregates. Rejecting suppresses it.
"""

from __future__ import annotations

import random

from sqlalchemy import func
from sqlmodel import Session, select

from .db import ENGINE
from .errors import ApiError
from .enums import Action, Cause, EventType
from .models import AuditEntry, BatchRun, Customer, Diagnosis, Execution, RevenueEvent, ReviewItem
from .outcome import draw_outcome
from .queries import now_iso
from .schemas import Execution as ExecutionSchema
from .schemas import ReviewDecisionResponse
from .schemas import ReviewItem as ReviewItemSchema


def apply_decision(event_id: str, decision: str) -> ReviewDecisionResponse:
    if decision not in ("approved", "rejected"):
        raise ApiError("validation", 422, "decision must be 'approved' or 'rejected'")

    with Session(ENGINE) as s:
        ri = s.get(ReviewItem, event_id)
        if ri is None:
            raise ApiError("not_found", 404, f"{event_id} is not in the review queue")
        if ri.status != "pending":
            raise ApiError("conflict", 409, f"{event_id} already {ri.status}")

        ex = s.get(Execution, event_id)
        ev = s.get(RevenueEvent, event_id)
        run = s.exec(select(BatchRun).order_by(BatchRun.id.desc())).first()

        ri.status = decision
        ri.decided_by = "operator"
        ri.decided_at = now_iso()

        if decision == "approved":
            cust = s.get(Customer, ev.customer_id)
            rng = random.Random((run.seed << 20) ^ int(event_id.split("_")[1]))
            outcome, recovered, cost = draw_outcome(
                event_type=EventType(ev.type),
                amount=ev.amount,
                true_cause=_safe_cause(ev.true_cause),
                action=Action(ri.action),
                responsiveness=cust.responsiveness,
                rng=rng,
            )
            ex.outcome = outcome.value
            ex.amount_recovered = recovered
            ex.outreach_cost = cost
        else:
            ex.outcome = "suppressed"
            ex.amount_recovered = 0
            ex.outreach_cost = 0
        ex.attempted_at = now_iso()

        n = s.exec(select(func.count(AuditEntry.id))).one()
        s.add(
            AuditEntry(
                id=f"aud_{n + 1:06d}",
                ts=now_iso(),
                event_id=event_id,
                stage="execute",
                actor="human",
                detail={"decision": decision, "action": ri.action, "amount_recovered": ex.amount_recovered},
            )
        )
        s.add(ri)
        s.add(ex)
        s.commit()
        s.refresh(ri)
        s.refresh(ex)

        _refresh_aggregates(s, run.id)
        result = ReviewDecisionResponse(
            item=ReviewItemSchema.model_validate(ri, from_attributes=True),
            execution=ExecutionSchema.model_validate(ex, from_attributes=True),
        )
    return result


def _refresh_aggregates(s: Session, run_id: int) -> None:
    run = s.get(BatchRun, run_id)
    execs = s.exec(select(Execution)).all()
    diags = {d.event_id: d.cause for d in s.exec(select(Diagnosis)).all()}
    events = {e.id: e.amount for e in s.exec(select(RevenueEvent)).all()}

    recovered = sum(x.amount_recovered for x in execs)
    outreach_cost = sum(x.outreach_cost for x in execs)
    at_risk = run.aggregates.get("revenue_at_risk") or sum(events.values()) or 1

    by_cause: dict[str, list[int]] = {}
    for x in execs:
        row = by_cause.setdefault(diags.get(x.event_id, "undetermined"), [0, 0])
        row[0] += events.get(x.event_id, 0)
        row[1] += x.amount_recovered

    pending = sum(1 for r in s.exec(select(ReviewItem)).all() if r.status == "pending")

    agg = dict(run.aggregates)
    agg["revenue_recovered"] = recovered
    agg["recovery_rate"] = round(recovered / at_risk, 4)
    agg["outreach_cost"] = outreach_cost
    agg["net_recovery"] = recovered - outreach_cost
    agg["cost_per_rupee_recovered"] = round(outreach_cost / recovered, 4) if recovered else 0.0
    agg["recovered_by_cause"] = [
        {"cause": c, "at_risk": v[0], "recovered": v[1]}
        for c, v in sorted(by_cause.items(), key=lambda kv: -kv[1][0])
    ]
    counters = dict(agg.get("compliance", {}))
    counters["awaiting_review"] = pending
    agg["compliance"] = counters

    run.aggregates = agg
    s.add(run)
    s.commit()


def _safe_cause(value: str) -> Cause:
    try:
        return Cause(value)
    except ValueError:
        return Cause.undetermined
