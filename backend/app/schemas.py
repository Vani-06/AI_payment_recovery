"""API + domain schemas (frozen contract) — Phase 0.

This module is the runtime source of truth for every shape crossing the wire.
Human copy: docs/CONTRACT.md + docs/DATA.md. TS copy: frontend/lib/types.ts.

Conventions:
- Money is a whole-INR ``int`` everywhere. Never a float, never paise.
- Timestamps are ISO-8601 UTC ``str`` (we keep them as strings end-to-end for the demo).
- ``*Masked`` models are what leaves the API for customer data — no real name, no hidden
  ``responsiveness``. The unmasked ``Customer`` never appears in a response.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import (
    Action,
    Actor,
    Cause,
    Channel,
    ChatIntent,
    ComplianceDisposition,
    ComplianceRuleId,
    EventType,
    LeakNodeKind,
    Mode,
    Outcome,
    ReviewStatus,
    Segment,
    Stage,
)

# ======================================================================================
# Core entities
# ======================================================================================


class Customer(BaseModel):
    """Full record. Lives in the DB only — never serialized into an API response."""

    id: str
    label: str  # "Customer #117" — the only identity the model / audit ever see
    name: str  # real name, UI-local only
    segment: Segment
    region: str
    method_pref: str
    dnd: bool = False
    opt_out: bool = False
    contact_count_7d: int = 0
    last_contacted_at: str | None = None
    promise_to_pay_date: str | None = None
    on_hold: bool = False
    responsiveness: float = Field(ge=0.0, le=1.0)  # hidden — outcome engine only


class CustomerMasked(BaseModel):
    """Safe projection for API responses and model prompts."""

    id: str
    label: str
    segment: Segment
    region: str
    method_pref: str
    dnd: bool
    opt_out: bool
    contact_count_7d: int
    last_contacted_at: str | None = None
    promise_to_pay_date: str | None = None
    on_hold: bool

    @classmethod
    def of(cls, c: Customer) -> "CustomerMasked":
        return cls(**c.model_dump(exclude={"name", "responsiveness"}))


class RevenueEvent(BaseModel):
    id: str
    type: EventType
    customer_id: str
    amount: int  # INR at risk
    currency: str = "INR"
    created_at: str
    gateway: str
    method: str
    issuer: str
    bin: str | None = None
    status: str
    true_cause: Cause  # hidden ground truth — see EventPublic for the wire shape
    meta: dict = Field(default_factory=dict)


class EventPublic(BaseModel):
    """RevenueEvent without the hidden ``true_cause``."""

    id: str
    type: EventType
    customer_id: str
    amount: int
    currency: str
    created_at: str
    gateway: str
    method: str
    issuer: str
    bin: str | None = None
    status: str
    meta: dict = Field(default_factory=dict)

    @classmethod
    def of(cls, e: RevenueEvent) -> "EventPublic":
        return cls(**e.model_dump(exclude={"true_cause"}))


class Triage(BaseModel):
    event_id: str
    expected_loss: int
    recoverability: float = Field(ge=0.0, le=1.0)
    priority: str  # "high" | "medium" | "low"


class Diagnosis(BaseModel):
    event_id: str
    cause: Cause  # chosen by deterministic analytics, NOT the LLM
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict = Field(default_factory=dict)  # the cross-batch stats behind `cause`
    narrative: str = ""  # LLM-written; empty until Phase 4


class Plan(BaseModel):
    event_id: str
    action: Action
    channel: Channel = Channel.none
    rationale: str = ""  # LLM-written; empty until Phase 4
    blocked_by: ComplianceRuleId | None = None


class Execution(BaseModel):
    event_id: str
    action: Action
    channel: Channel
    attempted_at: str
    outcome: Outcome
    amount_recovered: int = 0
    outreach_cost: int = 0


class ReviewItem(BaseModel):
    event_id: str
    action: Action
    rationale: str
    status: ReviewStatus = ReviewStatus.pending
    decided_by: str | None = None
    decided_at: str | None = None


class AuditEntry(BaseModel):
    id: str
    ts: str
    event_id: str
    stage: Stage
    actor: Actor
    detail: dict = Field(default_factory=dict)


# ======================================================================================
# Aggregates & derived views
# ======================================================================================


class RecoveredByCause(BaseModel):
    cause: Cause
    at_risk: int
    recovered: int


class ComplianceCounters(BaseModel):
    deferred: int = 0
    suppressed: int = 0
    stopped: int = 0
    escalated: int = 0
    auto_executed: int = 0
    awaiting_review: int = 0


class BatchAggregates(BaseModel):
    revenue_at_risk: int
    revenue_recovered: int
    recovery_rate: float
    baseline_recovery_rate: float
    outreach_cost: int
    net_recovery: int
    cost_per_rupee_recovered: float
    audit_coverage: float
    recovered_by_cause: list[RecoveredByCause]
    compliance: ComplianceCounters


class RunInfo(BaseModel):
    seed: int
    mode: Mode
    baseline: bool
    ran_at: str
    event_count: int


class EventRow(BaseModel):
    event_id: str
    customer_id: str
    customer_label: str
    type: EventType
    amount: int
    cause: Cause
    confidence: float
    action: Action
    compliance_status: ComplianceDisposition
    blocked_by: ComplianceRuleId | None = None
    outcome: Outcome
    amount_recovered: int


class EventTrace(BaseModel):
    event: EventPublic
    customer: CustomerMasked
    triage: Triage
    diagnosis: Diagnosis
    plan: Plan
    execution: Execution
    audit: list[AuditEntry]


class LeakNode(BaseModel):
    id: str
    label: str
    kind: LeakNodeKind
    value: int


class LeakEdge(BaseModel):
    source: str
    target: str
    rupees: int
    label: str = ""


class LeakGraph(BaseModel):
    nodes: list[LeakNode]
    edges: list[LeakEdge]


class ComplianceItem(BaseModel):
    event_id: str
    rule_id: ComplianceRuleId
    rule_label: str
    disposition: ComplianceDisposition
    detail: dict = Field(default_factory=dict)


class ComplianceReport(BaseModel):
    counters: ComplianceCounters
    items: list[ComplianceItem]


# ======================================================================================
# Request / response envelopes
# ======================================================================================


class HealthResponse(BaseModel):
    status: str = "ok"
    phase: str = "0"


class RunRequest(BaseModel):
    seed: int = 7
    mode: Mode = Mode.auto
    baseline: bool = False


class RunSummary(BaseModel):
    run: RunInfo
    aggregates: BatchAggregates


class ResultsResponse(BaseModel):
    run: RunInfo
    aggregates: BatchAggregates
    rows: list[EventRow]


class AuditResponse(BaseModel):
    entries: list[AuditEntry]
    total: int


class ReviewQueue(BaseModel):
    items: list[ReviewItem]


class ReviewDecisionRequest(BaseModel):
    decision: ReviewStatus  # only `approved` | `rejected` are valid inputs


class ReviewDecisionResponse(BaseModel):
    item: ReviewItem
    execution: Execution | None = None


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    intent: ChatIntent
    answer: str
    grounded_on: list[str] = Field(default_factory=list)


class ResetRequest(BaseModel):
    seed: int = 7


class ResetResponse(BaseModel):
    status: str = "reseeded"
    event_count: int


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
