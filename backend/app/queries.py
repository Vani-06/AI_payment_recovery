"""DB -> contract-shape read helpers — Phase 3.

Everything the read endpoints need, mapping the pipeline output tables to the frozen
wire schemas. The API layer stays thin on top of this.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from .config import settings
from .db import ENGINE
from .errors import ApiError
from .models import (
    AuditEntry,
    BatchRun,
    Customer,
    Diagnosis,
    Execution,
    Plan,
    ReviewItem,
    RevenueEvent,
)
from .schemas import (
    AuditResponse,
    BatchAggregates,
    ComplianceItem,
    ComplianceReport,
    CustomerMasked,
    EventPublic,
    EventRow,
    EventTrace,
    LeakGraph,
    ResultsResponse,
    ReviewQueue,
    RunInfo,
)
from .schemas import AuditEntry as AuditEntrySchema
from .schemas import Diagnosis as DiagnosisSchema
from .schemas import Execution as ExecutionSchema
from .schemas import Plan as PlanSchema
from .schemas import ReviewItem as ReviewItemSchema
from .schemas import Triage as TriageSchema

# execution.outcome -> ComplianceDisposition on the row
_DISPOSITION = {
    "recovered": "passed",
    "partial": "passed",
    "failed": "passed",
    "deferred": "deferred",
    "suppressed": "blocked",
    "awaiting_review": "awaiting_review",
}


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_batch() -> None:
    """Lazily run the demo batch so every read endpoint has data to serve."""
    with Session(ENGINE) as s:
        has_run = s.exec(select(BatchRun)).first() is not None
    if not has_run:
        from .pipeline import run_batch

        run_batch(settings.demo_seed, "auto", persist=True)


def _latest_run(s: Session) -> BatchRun:
    run = s.exec(select(BatchRun).order_by(BatchRun.id.desc())).first()
    if run is None:
        raise ApiError("not_found", 404, "no batch has been run yet")
    return run


def _run_info(run: BatchRun) -> RunInfo:
    return RunInfo(
        seed=run.seed,
        mode=run.mode,
        baseline=run.baseline,
        ran_at=run.ran_at,
        event_count=run.event_count,
    )


# ------------------------------------------------------------------------------------
# /results
# ------------------------------------------------------------------------------------


def build_results(
    limit: int = 400,
    offset: int = 0,
    outcome: str | None = None,
    cause: str | None = None,
) -> ResultsResponse:
    with Session(ENGINE) as s:
        run = _latest_run(s)
        events = s.exec(select(RevenueEvent)).all()
        customers = {c.id: c for c in s.exec(select(Customer)).all()}
        dg = {d.event_id: d for d in s.exec(select(Diagnosis)).all()}
        pl = {p.event_id: p for p in s.exec(select(Plan)).all()}
        ex = {x.event_id: x for x in s.exec(select(Execution)).all()}

    rows: list[EventRow] = []
    for e in events:
        d, p, x = dg.get(e.id), pl.get(e.id), ex.get(e.id)
        if not (d and p and x):
            continue
        row = EventRow(
            event_id=e.id,
            customer_id=e.customer_id,
            customer_label=customers[e.customer_id].label,
            type=e.type,
            amount=e.amount,
            cause=d.cause,
            confidence=d.confidence,
            action=p.action,
            compliance_status=_DISPOSITION.get(x.outcome, "passed"),
            blocked_by=p.blocked_by,
            outcome=x.outcome,
            amount_recovered=x.amount_recovered,
        )
        if outcome and row.outcome.value != outcome:
            continue
        if cause and row.cause.value != cause:
            continue
        rows.append(row)

    rows.sort(key=lambda r: r.amount, reverse=True)
    return ResultsResponse(
        run=_run_info(run),
        aggregates=BatchAggregates.model_validate(run.aggregates),
        rows=rows[offset : offset + limit],
    )


# ------------------------------------------------------------------------------------
# /event/{id}
# ------------------------------------------------------------------------------------


def build_event_trace(event_id: str) -> EventTrace:
    with Session(ENGINE, expire_on_commit=False) as s:
        e = s.get(RevenueEvent, event_id)
        if e is None:
            raise ApiError("not_found", 404, f"unknown event {event_id}")
        cust = s.get(Customer, e.customer_id)
        d = s.get(Diagnosis, event_id)
        p = s.get(Plan, event_id)
        x = s.get(Execution, event_id)
        audit = s.exec(
            select(AuditEntry).where(AuditEntry.event_id == event_id).order_by(AuditEntry.id)
        ).all()

        if not (cust and d and p and x):
            raise ApiError("not_found", 404, f"event {event_id} has no pipeline output — run a batch first")

        # Phase 4: fill LLM prose on first read, then persist so it's stable + cached.
        from . import narrate

        if not d.narrative:
            d.narrative = narrate.diagnosis_narrative(EventPublic.of(e).model_dump(), d.cause, d.confidence, d.evidence)
            s.add(d)
        if not p.rationale:
            p.rationale = narrate.plan_rationale(
                d.cause, p.action, p.channel, CustomerMasked.of(cust).model_dump(mode="json"), e.amount
            )
            s.add(p)
        s.commit()
        s.refresh(d)
        s.refresh(p)

    tri = next((a.detail for a in audit if a.stage == "triage"), {})
    return EventTrace(
        event=EventPublic.of(e),
        customer=CustomerMasked.of(cust),
        triage=TriageSchema(
            event_id=event_id,
            expected_loss=tri.get("expected_loss", e.amount),
            recoverability=tri.get("recoverability", 0.5),
            priority=tri.get("priority", "medium"),
        ),
        diagnosis=DiagnosisSchema(
            event_id=event_id, cause=d.cause, confidence=d.confidence, evidence=d.evidence, narrative=d.narrative
        ),
        plan=PlanSchema(event_id=event_id, action=p.action, channel=p.channel, rationale=p.rationale, blocked_by=p.blocked_by),
        execution=ExecutionSchema(
            event_id=event_id,
            action=x.action,
            channel=x.channel,
            attempted_at=x.attempted_at,
            outcome=x.outcome,
            amount_recovered=x.amount_recovered,
            outreach_cost=x.outreach_cost,
        ),
        audit=[AuditEntrySchema.model_validate(a, from_attributes=True) for a in audit],
    )


# ------------------------------------------------------------------------------------
# /graph  /audit  /compliance  /review
# ------------------------------------------------------------------------------------


def build_graph() -> LeakGraph:
    with Session(ENGINE) as s:
        return LeakGraph.model_validate(_latest_run(s).leak_graph)


def build_audit(
    event: str | None = None,
    stage: str | None = None,
    actor: str | None = None,
    outcome: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> AuditResponse:
    with Session(ENGINE) as s:
        q = select(AuditEntry)
        if event:
            q = q.where(AuditEntry.event_id == event)
        if stage:
            q = q.where(AuditEntry.stage == stage)
        if actor:
            q = q.where(AuditEntry.actor == actor)
        rows = s.exec(q.order_by(AuditEntry.id)).all()

    if outcome:
        rows = [r for r in rows if r.stage == "execute" and r.detail.get("outcome") == outcome]

    total = len(rows)
    page = rows[offset : offset + limit]
    return AuditResponse(
        entries=[AuditEntrySchema.model_validate(r, from_attributes=True) for r in page],
        total=total,
    )


def build_compliance() -> ComplianceReport:
    with Session(ENGINE) as s:
        agg = _latest_run(s).aggregates
    counters = agg.get("compliance", {})
    items = [ComplianceItem.model_validate(i) for i in agg.get("compliance_items", [])]
    return ComplianceReport(counters=counters, items=items)


def review_queue() -> ReviewQueue:
    with Session(ENGINE) as s:
        items = s.exec(select(ReviewItem).where(ReviewItem.status == "pending")).all()
    return ReviewQueue(items=[ReviewItemSchema.model_validate(i, from_attributes=True) for i in items])
