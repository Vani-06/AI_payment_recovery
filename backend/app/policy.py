"""Intervention policy — Phase 2.

``candidate_actions`` returns the escalation ladder for a diagnosed cause, filtered to
what makes sense for the event type. The runner walks the list through the compliance
engine, taking the first that passes (silent fixes first, outreach later), and falls to
``no_action_stop`` if none do.
"""

from __future__ import annotations

from .enums import Action, Cause, EventType

POLICY: dict[Cause, list[Action]] = {
    Cause.issuer_downtime: [Action.reroute_gateway, Action.smart_retry],
    Cause.gateway_degradation: [Action.reroute_gateway, Action.smart_retry],
    Cause.upi_timeout: [Action.smart_retry, Action.reroute_gateway, Action.payment_link_nudge],
    Cause.card_expired: [Action.update_card_link, Action.payment_link_nudge, Action.dunning_email],
    Cause.insufficient_funds_salary_cycle: [Action.retry_on_payday, Action.payment_link_nudge],
    Cause.checkout_latency: [Action.payment_link_nudge, Action.reroute_gateway],
    Cause.price_shock_shipping: [Action.coupon_offer, Action.payment_link_nudge],
    Cause.mandate_revoked: [Action.update_card_link, Action.finance_escalation, Action.payment_link_nudge, Action.dunning_email],
    Cause.forgot_to_pay: [Action.finance_escalation, Action.payment_link_nudge, Action.dunning_email],
    Cause.disputed: [Action.finance_escalation],  # compliance routes this to a human
    Cause.undetermined: [Action.smart_retry, Action.payment_link_nudge],
}

_VALID_FOR_TYPE: dict[EventType, set[Action]] = {
    EventType.payment_failed: {
        Action.smart_retry, Action.retry_on_payday, Action.reroute_gateway,
        Action.update_card_link, Action.payment_link_nudge, Action.dunning_email,
        Action.finance_escalation, Action.no_action_stop,
    },
    EventType.subscription_failed: {
        Action.smart_retry, Action.retry_on_payday, Action.reroute_gateway,
        Action.update_card_link, Action.payment_link_nudge, Action.dunning_email,
        Action.no_action_stop,
    },
    EventType.checkout_abandoned: {
        Action.payment_link_nudge, Action.coupon_offer, Action.reroute_gateway,
        Action.dunning_email, Action.no_action_stop,
    },
    EventType.invoice_overdue: {
        Action.payment_link_nudge, Action.dunning_email, Action.finance_escalation,
        Action.no_action_stop,
    },
}

_BASELINE_BY_TYPE: dict[EventType, Action] = {
    EventType.payment_failed: Action.smart_retry,
    EventType.subscription_failed: Action.smart_retry,
    EventType.checkout_abandoned: Action.payment_link_nudge,
    EventType.invoice_overdue: Action.dunning_email,
}


def candidate_actions(event_type: str, cause: str) -> list[Action]:
    et = EventType(event_type)
    valid = _VALID_FOR_TYPE[et]
    ladder = [a for a in POLICY.get(Cause(cause), [Action.smart_retry]) if a in valid]
    return ladder or [Action.no_action_stop]


def baseline_action(event_type: str) -> Action:
    return _BASELINE_BY_TYPE[EventType(event_type)]
