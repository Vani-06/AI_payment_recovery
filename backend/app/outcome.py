"""Deterministic outcome engine — Phase 1 (SPEC.md §7).

Given an event's hidden ``true_cause``, an action, the customer's hidden
``responsiveness``, and a seeded RNG, decide whether the action recovers the money.

Pure functions, no I/O. ``deferred`` / ``suppressed`` / ``awaiting_review`` are NOT
produced here — those come from the compliance engine in Phase 2.
"""

from __future__ import annotations

import random

from .config import CHANNEL_COST
from .enums import SILENT_ACTIONS, Action, Cause, Channel, EventType, Outcome

#: Base recovery probability at neutral responsiveness, per (cause, action).
#: Anything not listed falls to FLOOR. Right action for the cause ~0.6-0.85,
#: wrong action ~floor. Tune here in Phase 9.
AFFINITY: dict[Cause, dict[Action, float]] = {
    Cause.issuer_downtime: {Action.reroute_gateway: 0.80, Action.smart_retry: 0.35},
    Cause.gateway_degradation: {Action.reroute_gateway: 0.82, Action.smart_retry: 0.30},
    Cause.upi_timeout: {Action.smart_retry: 0.70, Action.reroute_gateway: 0.50, Action.payment_link_nudge: 0.42},
    Cause.card_expired: {
        Action.update_card_link: 0.78,
        Action.payment_link_nudge: 0.55,
        Action.dunning_email: 0.38,
        Action.smart_retry: 0.10,
    },
    Cause.insufficient_funds_salary_cycle: {
        Action.retry_on_payday: 0.62,
        Action.payment_link_nudge: 0.30,
        Action.smart_retry: 0.16,
    },
    Cause.checkout_latency: {Action.payment_link_nudge: 0.60, Action.reroute_gateway: 0.40, Action.coupon_offer: 0.40},
    Cause.price_shock_shipping: {Action.coupon_offer: 0.66, Action.payment_link_nudge: 0.34},
    Cause.mandate_revoked: {
        Action.update_card_link: 0.62,
        Action.finance_escalation: 0.60,
        Action.payment_link_nudge: 0.50,
        Action.dunning_email: 0.34,
    },
    Cause.forgot_to_pay: {
        Action.finance_escalation: 0.82,
        Action.payment_link_nudge: 0.58,
        Action.dunning_email: 0.46,
    },
    Cause.disputed: {Action.finance_escalation: 0.25},
    Cause.undetermined: {Action.smart_retry: 0.25, Action.reroute_gateway: 0.22},
}

FLOOR = 0.06
MAX_P = 0.97

#: Actions whose success is mostly process-driven, not customer-mood-driven (a B2B finance
#: follow-up behaves more like a silent fix than a consumer nudge).
LOW_VARIANCE_ACTIONS: frozenset[Action] = frozenset({Action.finance_escalation})

#: Which channel an action goes out on (drives outreach cost + the compliance rules).
CHANNEL_FOR_ACTION: dict[Action, Channel] = {
    Action.smart_retry: Channel.none,
    Action.retry_on_payday: Channel.none,
    Action.reroute_gateway: Channel.none,
    Action.no_action_stop: Channel.none,
    Action.update_card_link: Channel.whatsapp,
    Action.payment_link_nudge: Channel.whatsapp,
    Action.coupon_offer: Channel.whatsapp,
    Action.dunning_email: Channel.email,
    Action.finance_escalation: Channel.finance_touch,
}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def recovery_probability(cause: Cause, action: Action, responsiveness: float) -> float:
    """P(recover) for applying ``action`` to an event whose true cause is ``cause``.

    Silent actions (retry / reroute) barely depend on the customer; outreach actions
    scale strongly with responsiveness.
    """
    if action == Action.no_action_stop:
        return 0.0
    base = AFFINITY.get(cause, {}).get(action, FLOOR)
    if action in SILENT_ACTIONS:
        factor = 0.9 + 0.2 * responsiveness  # 0.9 .. 1.1
    elif action in LOW_VARIANCE_ACTIONS:
        factor = 0.82 + 0.18 * responsiveness  # 0.82 .. 1.0
    else:
        factor = 0.5 + 0.5 * responsiveness  # 0.5 .. 1.0
    return clamp(base * factor, 0.0, MAX_P)


def draw_outcome(
    *,
    event_type: EventType,
    amount: int,
    true_cause: Cause,
    action: Action,
    responsiveness: float,
    rng: random.Random,
) -> tuple[Outcome, int, int]:
    """Return ``(outcome, amount_recovered, outreach_cost)``.

    Overdue invoices that recover land as ``partial`` half the time (promise-to-pay).
    """
    channel = CHANNEL_FOR_ACTION.get(action, Channel.none)
    cost = CHANNEL_COST.get(channel, 0)

    if action == Action.no_action_stop:
        return Outcome.failed, 0, 0

    p = recovery_probability(true_cause, action, responsiveness)
    if rng.random() < p:
        if event_type == EventType.invoice_overdue and rng.random() < 0.35:
            frac = rng.uniform(0.4, 0.8)
            return Outcome.partial, round(amount * frac), cost
        return Outcome.recovered, amount, cost
    return Outcome.failed, 0, cost


def best_action(cause: Cause) -> Action:
    """Argmax-affinity action for a cause — the 'oracle' policy used to sanity-check
    that diagnosis-routed recovery beats a naive baseline. NOT the real planner (Phase 2)."""
    table = AFFINITY.get(cause)
    if not table:
        return Action.smart_retry
    return max(table, key=table.__getitem__)
