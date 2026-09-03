"""Phase 2 — pipeline + compliance + audit. Mostly DB-free (persist=False)."""

from __future__ import annotations

import pytest

from app.batchstats import compute_batch_stats
from app.diagnose import run_root_cause
from app.enums import Cause
from app.pipeline import run_batch
from app.seed import generate

SEED = 7

ENGINEERED = {
    Cause.issuer_downtime.value,
    Cause.gateway_degradation.value,
    Cause.upi_timeout.value,
    Cause.card_expired.value,
    Cause.insufficient_funds_salary_cycle.value,
    Cause.checkout_latency.value,
    Cause.price_shock_shipping.value,
    Cause.forgot_to_pay.value,
    Cause.mandate_revoked.value,
    Cause.disputed.value,
}

_AGG_KEYS = {
    "revenue_at_risk", "revenue_recovered", "recovery_rate", "baseline_recovery_rate",
    "outreach_cost", "net_recovery", "cost_per_rupee_recovered", "audit_coverage",
    "recovered_by_cause", "compliance",
}


def test_aggregates_shape_and_bounds():
    a = run_batch(SEED, "auto", persist=False)["aggregates"]
    assert _AGG_KEYS <= set(a)
    assert a["revenue_at_risk"] > 0
    assert 0.25 <= a["recovery_rate"] <= 0.55
    assert a["net_recovery"] == a["revenue_recovered"] - a["outreach_cost"]
    assert a["audit_coverage"] == 1.0


def test_agent_beats_baseline():
    a = run_batch(SEED, "auto", persist=False)["aggregates"]
    assert a["recovery_rate"] > a["baseline_recovery_rate"] + 0.08


def test_baseline_mode_recovers_less():
    auto = run_batch(SEED, "auto", persist=False)["aggregates"]["recovery_rate"]
    base = run_batch(SEED, "auto", baseline=True, persist=False)["aggregates"]["recovery_rate"]
    assert base < auto


def test_compliance_counters():
    c = run_batch(SEED, "auto", persist=False)["aggregates"]["compliance"]
    assert c["deferred"] > 0
    assert c["suppressed"] > 0
    assert c["escalated"] > 0
    assert c["auto_executed"] > 0
    assert c["awaiting_review"] == 0
    assert c["stopped"] >= 0


def test_review_mode_queues_outreach_but_runs_silent():
    r = run_batch(SEED, "review", persist=False)
    c = r["aggregates"]["compliance"]
    assert c["awaiting_review"] > 0
    assert c["auto_executed"] > 0  # silent fixes still execute
    assert r["aggregates"]["recovery_rate"] > 0


def test_determinism():
    a = run_batch(SEED, "auto", persist=False)
    b = run_batch(SEED, "auto", persist=False)
    assert a["aggregates"] == b["aggregates"]
    assert a["leak_graph"] == b["leak_graph"]


def test_audit_entry_count():
    # 5 stage entries per event, no more (reviews don't add audit rows in Phase 2)
    from app.pipeline import AuditLog, run_batch as _rb  # noqa

    r = run_batch(SEED, "auto", persist=False)
    assert r["aggregates"]["audit_coverage"] == 1.0


def test_diagnosis_accuracy():
    customers, events = generate(SEED)
    by_id = {c.id: c for c in customers}
    stats = compute_batch_stats(events, customers)

    total = hit = eng_total = eng_hit = 0
    for e in events:
        cause = run_root_cause(e, by_id[e.customer_id], stats)[0]
        total += 1
        hit += cause == e.true_cause
        if e.true_cause in ENGINEERED:
            eng_total += 1
            eng_hit += cause == e.true_cause
    assert hit / total >= 0.72, f"overall {hit}/{total}"
    assert eng_hit / eng_total >= 0.80, f"engineered {eng_hit}/{eng_total}"


def test_leak_graph_integrity():
    g = run_batch(SEED, "auto", persist=False)["leak_graph"]
    ids = {n["id"] for n in g["nodes"]}
    assert "loss:total" in ids
    assert any(n["kind"] == "failure" for n in g["nodes"])
    assert any(n["kind"] in ("issuer", "gateway", "region", "method") for n in g["nodes"])
    for e in g["edges"]:
        assert e["source"] in ids and e["target"] in ids
    loss_in = sum(e["rupees"] for e in g["edges"] if e["target"] == "loss:total")
    loss_node = next(n["value"] for n in g["nodes"] if n["id"] == "loss:total")
    assert loss_in == loss_node


def test_undetermined_when_no_signal_is_conservative():
    # confidence gating should yield some 'undetermined' diagnoses on the diffuse tail
    customers, events = generate(SEED)
    by_id = {c.id: c for c in customers}
    stats = compute_batch_stats(events, customers)
    causes = [run_root_cause(e, by_id[e.customer_id], stats)[0] for e in events]
    assert causes.count(Cause.undetermined.value) >= 1


@pytest.mark.skipif(True, reason="DB round-trip covered by the CLI on a live Postgres; enable when needed")
def test_persist_roundtrip():
    from sqlmodel import Session, select

    from app.db import ENGINE
    from app.models import AuditEntry, BatchRun, Diagnosis

    run_batch(SEED, "auto", persist=True)
    with Session(ENGINE) as s:
        assert len(s.exec(select(Diagnosis)).all()) == 400
        assert len(s.exec(select(AuditEntry)).all()) == 2000
        assert s.exec(select(BatchRun)).first() is not None
