"""Phase 3 — HTTP API. Requires a reachable Postgres (skips the whole module otherwise)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import ENGINE


def _db_up() -> bool:
    try:
        with ENGINE.connect() as c:
            c.exec_driver_sql("select 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="Postgres not reachable")

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_run_then_results():
    r = client.post("/run", json={"seed": 7, "mode": "auto", "baseline": False})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"run", "aggregates"}
    assert body["run"]["event_count"] == 400

    r = client.get("/results")
    assert r.status_code == 200
    res = r.json()
    assert len(res["rows"]) == 400
    a = res["aggregates"]
    assert 0.25 <= a["recovery_rate"] <= 0.55
    assert a["recovery_rate"] > a["baseline_recovery_rate"]
    assert res["run"]["seed"] == 7


def test_results_filters():
    assert len(client.get("/results?limit=5").json()["rows"]) == 5
    rec = client.get("/results?outcome=recovered").json()["rows"]
    assert rec and all(row["outcome"] == "recovered" for row in rec)
    iss = client.get("/results?cause=issuer_downtime").json()["rows"]
    assert iss and all(row["cause"] == "issuer_downtime" for row in iss)


def test_event_trace_and_masking():
    eid = client.get("/results?limit=1").json()["rows"][0]["event_id"]
    r = client.get(f"/event/{eid}")
    assert r.status_code == 200
    t = r.json()
    assert set(t) == {"event", "customer", "triage", "diagnosis", "plan", "execution", "audit"}
    assert "true_cause" not in t["event"]
    assert "name" not in t["customer"] and "responsiveness" not in t["customer"]
    assert len(t["audit"]) >= 5
    assert t["diagnosis"]["cause"] and t["triage"]["priority"] in {"high", "medium", "low"}


def test_event_404():
    r = client.get("/event/evt_99999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_graph():
    g = client.get("/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    assert "loss:total" in ids
    assert any(n["kind"] == "failure" for n in g["nodes"])
    for e in g["edges"]:
        assert e["source"] in ids and e["target"] in ids


def test_audit_filters():
    a = client.get("/audit?stage=root_cause").json()
    assert a["total"] == 400
    assert all(e["stage"] == "root_cause" for e in a["entries"])
    comp = client.get("/audit?actor=compliance&limit=10").json()
    assert all(e["actor"] == "compliance" for e in comp["entries"])
    eid = client.get("/results?limit=1").json()["rows"][0]["event_id"]
    one = client.get(f"/audit?event={eid}").json()
    assert one["total"] >= 5 and all(e["event_id"] == eid for e in one["entries"])


def test_compliance():
    c = client.get("/compliance").json()
    assert c["counters"]["escalated"] > 0
    assert c["counters"]["deferred"] > 0
    assert isinstance(c["items"], list) and c["items"]
    assert {"event_id", "rule_id", "rule_label", "disposition"} <= set(c["items"][0])


def test_review_flow():
    assert client.post("/run", json={"seed": 7, "mode": "review"}).status_code == 200
    queue = client.get("/review").json()["items"]
    assert len(queue) > 0
    target = queue[0]["event_id"]

    r = client.post(f"/review/{target}", json={"decision": "approved"})
    assert r.status_code == 200
    body = r.json()
    assert body["item"]["status"] == "approved"
    assert body["execution"] is not None

    assert all(i["event_id"] != target for i in client.get("/review").json()["items"])
    assert client.post(f"/review/{target}", json={"decision": "approved"}).status_code == 409

    # awaiting_review counter dropped by at least one
    assert client.get("/compliance").json()["counters"]["awaiting_review"] == len(queue) - 1

    # bad decision value
    other = client.get("/review").json()["items"][0]["event_id"]
    assert client.post(f"/review/{other}", json={"decision": "pending"}).status_code == 422

    client.post("/run", json={"seed": 7, "mode": "auto"})  # leave DB in auto state


def test_chat():
    why = client.post("/chat", json={"question": "why is revenue down this week?"}).json()
    assert why["intent"] == "why_down" and "at risk" in why["answer"].lower()

    cid = client.get("/results?limit=1").json()["rows"][0]["customer_id"]
    detail = client.post("/chat", json={"question": f"what did you do for {cid}?"}).json()
    assert detail["intent"] == "customer_detail" and cid.split("_")[1].lstrip("0") in detail["answer"]

    top = client.post("/chat", json={"question": "what are the top causes?"}).json()
    assert top["intent"] == "top_causes"


def test_admin_reset():
    r = client.post("/admin/reset", json={"seed": 7})
    assert r.status_code == 200
    assert r.json() == {"status": "reseeded", "event_count": 400}
