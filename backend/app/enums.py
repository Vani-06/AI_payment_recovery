"""Frozen enums — Phase 0.

Mirror of docs/DATA.md. The TS mirror is frontend/lib/types.ts.
Change all three together. Everything downstream imports names from here; never inline a
literal like "issuer_downtime" elsewhere.
"""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    payment_failed = "payment_failed"
    checkout_abandoned = "checkout_abandoned"
    invoice_overdue = "invoice_overdue"
    subscription_failed = "subscription_failed"


class Cause(str, Enum):
    card_expired = "card_expired"
    insufficient_funds_salary_cycle = "insufficient_funds_salary_cycle"
    issuer_downtime = "issuer_downtime"
    gateway_degradation = "gateway_degradation"
    upi_timeout = "upi_timeout"
    checkout_latency = "checkout_latency"
    price_shock_shipping = "price_shock_shipping"
    mandate_revoked = "mandate_revoked"
    forgot_to_pay = "forgot_to_pay"
    disputed = "disputed"
    undetermined = "undetermined"  # only from confidence gating (SPEC §16); never seeded


class Action(str, Enum):
    smart_retry = "smart_retry"
    retry_on_payday = "retry_on_payday"
    reroute_gateway = "reroute_gateway"
    update_card_link = "update_card_link"
    payment_link_nudge = "payment_link_nudge"
    dunning_email = "dunning_email"
    coupon_offer = "coupon_offer"
    finance_escalation = "finance_escalation"
    no_action_stop = "no_action_stop"


#: Actions that never contact the customer — exempt from the outreach compliance rules.
SILENT_ACTIONS: frozenset[Action] = frozenset(
    {Action.smart_retry, Action.retry_on_payday, Action.reroute_gateway, Action.no_action_stop}
)


class Channel(str, Enum):
    whatsapp = "whatsapp"
    email = "email"
    sms = "sms"
    voice = "voice"
    finance_touch = "finance_touch"
    none = "none"


class Outcome(str, Enum):
    recovered = "recovered"
    partial = "partial"
    failed = "failed"
    deferred = "deferred"
    suppressed = "suppressed"
    awaiting_review = "awaiting_review"


class Stage(str, Enum):
    triage = "triage"
    root_cause = "root_cause"
    plan = "plan"
    compliance = "compliance"
    execute = "execute"
    audit = "audit"


class Actor(str, Enum):
    agent = "agent"
    compliance = "compliance"
    system = "system"
    human = "human"


class Mode(str, Enum):
    auto = "auto"
    review = "review"


class Segment(str, Enum):
    b2c = "b2c"
    b2b = "b2b"


class ComplianceRuleId(str, Enum):
    contact_cap = "contact_cap"
    channel_cooldown = "channel_cooldown"
    quiet_hours = "quiet_hours"
    dnd_optout = "dnd_optout"
    promise_to_pay_hold = "promise_to_pay_hold"
    manual_hold_dispute = "manual_hold_dispute"
    discount_guardrail = "discount_guardrail"
    economic_stop = "economic_stop"
    global_batch_cap = "global_batch_cap"
    review_mode_gate = "review_mode_gate"


#: Human-readable labels for the Compliance panel.
COMPLIANCE_RULE_LABELS: dict[ComplianceRuleId, str] = {
    ComplianceRuleId.contact_cap: "Contact cap (max 3 / customer / 7 days)",
    ComplianceRuleId.channel_cooldown: "Channel cooldown (1 outreach / 24h)",
    ComplianceRuleId.quiet_hours: "Quiet hours (21:00-09:00 IST)",
    ComplianceRuleId.dnd_optout: "DND / opt-out honored",
    ComplianceRuleId.promise_to_pay_hold: "Promise-to-pay hold",
    ComplianceRuleId.manual_hold_dispute: "Manual hold / dispute -> human",
    ComplianceRuleId.discount_guardrail: "Discount guardrail",
    ComplianceRuleId.economic_stop: "Economic stop (contact cost > recoverable)",
    ComplianceRuleId.global_batch_cap: "Global batch outreach cap",
    ComplianceRuleId.review_mode_gate: "Review Mode — awaiting human approval",
}


class ComplianceDisposition(str, Enum):
    passed = "passed"
    blocked = "blocked"
    deferred = "deferred"
    awaiting_review = "awaiting_review"


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LeakNodeKind(str, Enum):
    gateway = "gateway"
    issuer = "issuer"
    method = "method"
    region = "region"
    failure = "failure"
    loss = "loss"


class ChatIntent(str, Enum):
    why_down = "why_down"
    customer_detail = "customer_detail"
    top_causes = "top_causes"
    unknown = "unknown"
