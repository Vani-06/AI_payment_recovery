"""Phase 4 — LLM layer. Runs entirely on the template fallback path (no API key needed)."""

from __future__ import annotations

import pytest

from app import narrate
from app.llm import LLMError, llm, llm_available


def test_llm_raises_without_key():
    # this suite assumes no ANTHROPIC_API_KEY in the test env
    if llm_available():
        pytest.skip("API key present")
    with pytest.raises(LLMError):
        llm("sys", "prompt")


def test_diagnosis_narrative_fallback_mentions_cause():
    ev = {"type": "payment_failed", "amount": 4999, "gateway": "razorpay_pg_a", "method": "upi", "issuer": "ICICI"}
    evidence = {"signal": "issuer_incident", "issuer": "ICICI", "issuer_lift": 3.2, "window_share": 0.9, "window_events": 40}
    out = narrate.diagnosis_narrative(ev, "issuer_downtime", 0.9, evidence)
    assert isinstance(out, str) and len(out) > 20
    assert "issuer downtime" in out.lower()
    assert "ICICI" in out


def test_plan_rationale_fallback():
    cust = {"segment": "b2c", "region": "south", "on_hold": False, "promise_to_pay_date": None, "dnd": False, "opt_out": False}
    out = narrate.plan_rationale("issuer_downtime", "reroute_gateway", "none", cust, 4999)
    assert isinstance(out, str) and "reroute" in out.lower()


def test_narrative_cache_is_stable():
    ev = {"type": "checkout_abandoned", "amount": 2650, "gateway": "razorpay_pg_a", "method": "card", "issuer": "Visa"}
    evd = {"signal": "shipping_shock", "shipping_fee": 400, "shipping_ratio": 0.3}
    a = narrate.diagnosis_narrative(ev, "price_shock_shipping", 0.7, evd)
    b = narrate.diagnosis_narrative(ev, "price_shock_shipping", 0.7, evd)
    assert a == b
    assert narrate._CACHE_PATH.exists()


# --- API-level (needs Postgres) --------------------------------------------------

from app.db import ENGINE  # noqa: E402


def _db_up() -> bool:
    try:
        with ENGINE.connect() as c:
            c.exec_driver_sql("select 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_up(), reason="Postgres not reachable")
def test_event_trace_gets_prose():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    client.post("/run", json={"seed": 7, "mode": "auto"})
    eid = client.get("/results?limit=1").json()["rows"][0]["event_id"]
    t = client.get(f"/event/{eid}").json()
    assert t["diagnosis"]["narrative"].strip()
    assert t["plan"]["rationale"].strip()
    # persisted: a second read returns the same text
    t2 = client.get(f"/event/{eid}").json()
    assert t2["diagnosis"]["narrative"] == t["diagnosis"]["narrative"]


@pytest.mark.skipif(not _db_up(), reason="Postgres not reachable")
def test_chat_templated_without_llm():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    client.post("/run", json={"seed": 7, "mode": "auto"})
    r = client.post("/chat", json={"question": "why is revenue down?"}).json()
    assert r["intent"] == "why_down"
    assert "at risk" in r["answer"].lower()
