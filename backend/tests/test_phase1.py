"""Phase 1 domain-core checks. No DB — everything runs off ``generate()`` in memory."""

from __future__ import annotations

from app.analysis import summarize
from app.enums import Action, Cause, EventType
from app.outcome import best_action, draw_outcome, recovery_probability
from app.seed import N_CUSTOMERS, N_EVENTS, generate

SEED = 7


def _tuples(events):
    return [(e.id, e.true_cause, e.amount, e.customer_id) for e in events]


def test_counts():
    customers, events = generate(SEED)
    assert len(customers) == N_CUSTOMERS
    assert len(events) == N_EVENTS


def test_determinism():
    ca, ea = generate(SEED)
    cb, eb = generate(SEED)
    assert _tuples(ea) == _tuples(eb)
    assert [(c.id, c.responsiveness, c.region) for c in ca] == [(c.id, c.responsiveness, c.region) for c in cb]


def test_different_seed_differs():
    _, e7 = generate(7)
    _, e8 = generate(8)
    assert _tuples(e7) != _tuples(e8)


def test_event_ids_sorted_and_unique():
    _, events = generate(SEED)
    ids = [e.id for e in events]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
    times = [e.created_at for e in events]
    assert times == sorted(times)


def test_engineered_skews_present():
    _, events = generate(SEED)
    icici_downtime = [e for e in events if e.true_cause == Cause.issuer_downtime.value]
    assert len(icici_downtime) >= 40
    assert all(e.issuer == "ICICI" for e in icici_downtime)

    upi = [e for e in events if e.true_cause == Cause.upi_timeout.value]
    assert sum(1 for e in upi if e.meta.get("device") == "android") >= 40

    invoices = [e for e in events if e.type == EventType.invoice_overdue.value]
    assert len(invoices) == 48
    assert max(e.amount for e in invoices) > 100_000  # invoices dominate at-risk


def test_customers_masked_fields_exist():
    customers, _ = generate(SEED)
    assert any(c.promise_to_pay_date for c in customers)
    assert any(c.opt_out for c in customers)
    assert all(0.0 <= c.responsiveness <= 1.0 for c in customers)


def test_recovery_probability_bounds_and_ordering():
    # right action for the cause must beat a wrong one at the same responsiveness
    p_right = recovery_probability(Cause.issuer_downtime, Action.reroute_gateway, 0.5)
    p_wrong = recovery_probability(Cause.issuer_downtime, Action.dunning_email, 0.5)
    assert 0.0 <= p_wrong < p_right <= 0.97
    assert recovery_probability(Cause.card_expired, Action.no_action_stop, 0.9) == 0.0


def test_draw_outcome_deterministic():
    import random

    kw = dict(
        event_type=EventType.payment_failed,
        amount=5000,
        true_cause=Cause.issuer_downtime,
        action=Action.reroute_gateway,
        responsiveness=0.6,
    )
    a = draw_outcome(rng=random.Random(1), **kw)
    b = draw_outcome(rng=random.Random(1), **kw)
    assert a == b


def test_oracle_beats_baseline():
    s = summarize(SEED)
    o, b = s["oracle"]["rate"], s["baseline"]["rate"]
    assert o - b > 0.10, f"oracle {o:.3f} vs baseline {b:.3f}"
    assert 0.30 <= o <= 0.55, f"oracle rate out of expected band: {o:.3f}"


def test_best_action_is_argmax():
    assert best_action(Cause.price_shock_shipping) == Action.coupon_offer
    assert best_action(Cause.gateway_degradation) == Action.reroute_gateway
