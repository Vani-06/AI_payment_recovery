"""Compliance / stopping-rules engine — Phase 2 (SPEC.md §8).

Every planned action passes through ``ComplianceEngine.resolve`` before execution. It
holds mutable batch state (contact counters, cooldowns, coupon use, global outreach
count) and walks the candidate ladder: silent fixes pass rules 2-9 automatically; the
first outreach candidate that clears all rules wins; if none do, the event stops.

Rule 10 (Review Mode) is applied last, so silent fixes still auto-execute in review mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .batchstats import parse_ts
from .config import (
    CHANNEL_COOLDOWN_HOURS,
    CHANNEL_COST,
    CONTACT_CAP_PER_7D,
    FINANCE_MIN_INR,
    FRESH_CONTACT_WINDOW_HOURS,
    GLOBAL_OUTREACH_CAP,
    MIN_EXPECTED_RECOVERY_INR,
    QUIET_HOURS_END,
    QUIET_HOURS_START,
)
from .enums import (
    SILENT_ACTIONS,
    Action,
    Cause,
    Channel,
    ComplianceDisposition,
    ComplianceRuleId,
    Mode,
)
from .models import Customer, RevenueEvent
from .outcome import CHANNEL_FOR_ACTION, recovery_probability

_IST = timedelta(hours=5, minutes=30)

# block kind -> (disposition, counter key)
_KIND = {
    "deferred": (ComplianceDisposition.deferred, "deferred"),
    "suppressed": (ComplianceDisposition.blocked, "suppressed"),
    "stopped": (ComplianceDisposition.blocked, "stopped"),
}


@dataclass
class Decision:
    action: Action
    channel: Channel
    disposition: ComplianceDisposition
    rule_id: ComplianceRuleId | None = None
    detail: dict = field(default_factory=dict)


class ComplianceEngine:
    def __init__(self, customers: list[Customer], now: datetime):
        self.now = now
        self.contact_7d = {c.id: int(c.contact_count_7d or 0) for c in customers}
        self.last_contact: dict[str, datetime] = {
            c.id: parse_ts(c.last_contacted_at) for c in customers if c.last_contacted_at
        }
        self.coupon_used: set[str] = set()
        self.outreach_count = 0
        self.counters: dict[str, int] = {
            "deferred": 0,
            "suppressed": 0,
            "stopped": 0,
            "escalated": 0,
            "auto_executed": 0,
            "awaiting_review": 0,
        }
        self.items: list[dict] = []

    # -- public ------------------------------------------------------------------
    def resolve(
        self,
        event: RevenueEvent,
        customer: Customer,
        cause: str,
        candidates: list[Action],
        mode: str,
    ) -> Decision:
        # Rule 1 — manual hold / dispute: no automated action at all.
        if customer.on_hold or cause == Cause.disputed.value:
            self.counters["escalated"] += 1
            detail = {"on_hold": customer.on_hold, "cause": cause}
            self._log(event.id, ComplianceRuleId.manual_hold_dispute, ComplianceDisposition.blocked, detail)
            return Decision(
                Action.finance_escalation, Channel.finance_touch,
                ComplianceDisposition.blocked, ComplianceRuleId.manual_hold_dispute, detail,
            )

        first_block: tuple[ComplianceRuleId, dict, str] | None = None
        for action in candidates:
            if action in SILENT_ACTIONS:
                return Decision(action, Channel.none, ComplianceDisposition.passed)

            channel = CHANNEL_FOR_ACTION.get(action, Channel.none)
            block = self._outreach_block(event, customer, cause, action, channel)
            if block is None:
                if mode == Mode.review.value:
                    self.counters["awaiting_review"] += 1
                    self._log(event.id, ComplianceRuleId.review_mode_gate, ComplianceDisposition.awaiting_review, {"action": action.value})
                    return Decision(action, channel, ComplianceDisposition.awaiting_review, ComplianceRuleId.review_mode_gate)
                return Decision(action, channel, ComplianceDisposition.passed)
            if first_block is None:
                first_block = block

        # every candidate blocked -> stop, reported with the primary action's reason
        rule_id, detail, kind = first_block  # type: ignore[misc]
        disposition, counter = _KIND[kind]
        self.counters[counter] += 1
        self._log(event.id, rule_id, disposition, detail)
        return Decision(Action.no_action_stop, Channel.none, disposition, rule_id, detail)

    def record_outreach(self, customer_id: str, action: Action) -> None:
        """Called by the runner after an outreach action actually executes.

        Bumps the 7-day contact count (so ``contact_cap`` bounds within-batch volume) but
        does NOT touch ``last_contact`` — cooldown is about not re-messaging for the *same*
        incident; distinct failures in the window each warrant their own outreach.
        """
        self.contact_7d[customer_id] = self.contact_7d.get(customer_id, 0) + 1
        self.outreach_count += 1
        if action == Action.coupon_offer:
            self.coupon_used.add(customer_id)

    # -- rules 2-9 -------------------------------------------------------------
    def _outreach_block(
        self, event: RevenueEvent, cust: Customer, cause: str, action: Action, channel: Channel
    ) -> tuple[ComplianceRuleId, dict, str] | None:
        # 2 — DND / opt-out
        if cust.dnd or cust.opt_out:
            return ComplianceRuleId.dnd_optout, {"dnd": cust.dnd, "opt_out": cust.opt_out}, "suppressed"

        # 3 — promise-to-pay hold
        if cust.promise_to_pay_date and parse_ts(cust.promise_to_pay_date) > self.now:
            return ComplianceRuleId.promise_to_pay_hold, {"until": cust.promise_to_pay_date}, "deferred"

        # 4 — quiet hours (notional send time: event time if fresh, else "now")
        send_at = self._send_time(event)
        ist_hour = (send_at + _IST).hour
        if ist_hour >= QUIET_HOURS_START or ist_hour < QUIET_HOURS_END:
            return ComplianceRuleId.quiet_hours, {"send_local_time": (send_at + _IST).strftime("%H:%M"), "window": "21:00-09:00 IST"}, "deferred"

        # 5 — channel cooldown
        lc = self.last_contact.get(cust.id)
        if lc and (self.now - lc) < timedelta(hours=CHANNEL_COOLDOWN_HOURS):
            return ComplianceRuleId.channel_cooldown, {"hours_since_last": round((self.now - lc).total_seconds() / 3600, 1)}, "deferred"

        # 6 — contact cap
        if self.contact_7d.get(cust.id, 0) >= CONTACT_CAP_PER_7D:
            return ComplianceRuleId.contact_cap, {"contacts_7d": self.contact_7d[cust.id], "cap": CONTACT_CAP_PER_7D}, "suppressed"

        # 7 — discount guardrail (single coupon per customer)
        if action == Action.coupon_offer and cust.id in self.coupon_used:
            return ComplianceRuleId.discount_guardrail, {"reason": "coupon already used"}, "suppressed"

        # 8 — economic stop: not worth a reviewed outreach touch below the expected-value floor
        send_cost = CHANNEL_COST.get(channel, 0)
        p = recovery_probability(_as_cause(cause), action, cust.responsiveness)
        expected = event.amount * p
        if (
            expected < MIN_EXPECTED_RECOVERY_INR
            or expected < send_cost
            or (action == Action.finance_escalation and event.amount < FINANCE_MIN_INR)
        ):
            return (
                ComplianceRuleId.economic_stop,
                {"expected_recovery": round(expected), "floor": MIN_EXPECTED_RECOVERY_INR, "channel": channel.value},
                "stopped",
            )

        # 9 — global batch cap
        if self.outreach_count >= GLOBAL_OUTREACH_CAP:
            return ComplianceRuleId.global_batch_cap, {"cap": GLOBAL_OUTREACH_CAP}, "stopped"

        return None

    # -- helpers ------------------------------------------------------------------
    def _send_time(self, event: RevenueEvent) -> datetime:
        created = parse_ts(event.created_at)
        if (self.now - created) <= timedelta(hours=FRESH_CONTACT_WINDOW_HOURS):
            return created
        return self.now

    def _log(self, event_id: str, rule: ComplianceRuleId, disp: ComplianceDisposition, detail: dict) -> None:
        from .enums import COMPLIANCE_RULE_LABELS

        self.items.append(
            {
                "event_id": event_id,
                "rule_id": rule.value,
                "rule_label": COMPLIANCE_RULE_LABELS[rule],
                "disposition": disp.value,
                "detail": detail,
            }
        )


def _as_cause(cause: str) -> Cause:
    try:
        return Cause(cause)
    except ValueError:
        return Cause.undetermined
