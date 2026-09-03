# API Contract (frozen — Phase 0)

Base URL: `http://localhost:8000`. All bodies JSON. Enum values: see [DATA.md](DATA.md).
Money = whole INR integers. This document is authoritative for shapes; `schemas.py` is
authoritative for validation. Change together.

Endpoints marked **P0** exist after Phase 0; the rest are stubbed to return the fixture or
`501` until their phase.

| Method | Path | Phase | Purpose |
|---|---|---|---|
| GET | `/health` | **P0** | liveness |
| POST | `/run` | P3 | run a batch, persist, return summary |
| GET | `/results` | **P0*** | aggregates + event rows (*P0 serves the fixture) |
| GET | `/event/{id}` | P3 | full per-event stage trace |
| GET | `/graph` | P3 | leak-graph nodes + edges |
| GET | `/audit` | P3 | filtered append-only audit log |
| GET | `/compliance` | P3 | compliance counters + blocked/deferred items |
| GET | `/review` | P3 | pending review queue (Review Mode) |
| POST | `/review/{event_id}` | P3 | approve / reject a queued action |
| POST | `/chat` | P4 | grounded Q&A over the current batch |
| POST | `/admin/reset` | P3 | wipe + reseed (demo convenience) |

---

## GET /health
`200` → `{ "status": "ok", "phase": "0" }`

---

## POST /run
Request:
```json
{ "seed": 7, "mode": "auto", "baseline": false }
```
- `seed` int, default 7 · `mode` `"auto"|"review"`, default `"auto"` · `baseline` bool,
  default `false` (true = force naive "retry/contact everything", for the comparison).

Response `200`:
```json
{
  "run": { "seed": 7, "mode": "auto", "baseline": false,
           "ran_at": "2026-09-04T10:00:00Z", "event_count": 400 },
  "aggregates": { "...": "see BatchAggregates below" }
}
```

---

## GET /results
Query: `?limit` (default 400) · `?offset` (default 0) · `?outcome` · `?cause` (filters rows).

Response `200`:
```json
{
  "run": { "seed": 7, "mode": "auto", "baseline": false,
           "ran_at": "2026-09-04T10:00:00Z", "event_count": 400 },
  "aggregates": {
    "revenue_at_risk": 1243000,
    "revenue_recovered": 486000,
    "recovery_rate": 0.391,
    "baseline_recovery_rate": 0.242,
    "outreach_cost": 7000,
    "net_recovery": 479000,
    "cost_per_rupee_recovered": 0.0144,
    "audit_coverage": 1.0,
    "recovered_by_cause": [
      { "cause": "issuer_downtime", "at_risk": 410000, "recovered": 180000 }
    ],
    "compliance": {
      "deferred": 22, "suppressed": 8, "stopped": 14,
      "escalated": 6, "auto_executed": 210, "awaiting_review": 0
    }
  },
  "rows": [
    {
      "event_id": "evt_00042", "customer_id": "cus_0117",
      "customer_label": "Customer #117", "type": "payment_failed",
      "amount": 4999, "cause": "issuer_downtime", "confidence": 0.86,
      "action": "reroute_gateway", "compliance_status": "passed",
      "blocked_by": null, "outcome": "recovered", "amount_recovered": 4999
    }
  ]
}
```
Before the first `/run`, P0 returns the committed `fixtures/sample_results.json` unchanged.

---

## GET /event/{id}
Response `200` (`EventTrace`):
```json
{
  "event": { "id": "evt_00042", "type": "payment_failed", "customer_id": "cus_0117",
             "amount": 4999, "currency": "INR", "created_at": "2026-09-03T18:22:00Z",
             "gateway": "razorpay_pg_a", "method": "upi", "issuer": "ICICI",
             "bin": null, "status": "failed", "meta": { "attempt_no": 1 } },
  "customer": { "id": "cus_0117", "label": "Customer #117", "segment": "b2c",
                "region": "south", "method_pref": "upi", "dnd": false, "opt_out": false,
                "contact_count_7d": 1, "last_contacted_at": null,
                "promise_to_pay_date": null, "on_hold": false },
  "triage": { "expected_loss": 4999, "recoverability": 0.7, "priority": "high" },
  "diagnosis": { "event_id": "evt_00042", "cause": "issuer_downtime", "confidence": 0.86,
                 "evidence": { "issuer_fail_rate": 0.41, "baseline_fail_rate": 0.06,
                               "affected_region": "south", "window": "18:00-19:30" },
                 "narrative": "" },
  "plan": { "event_id": "evt_00042", "action": "reroute_gateway", "channel": "none",
            "rationale": "", "blocked_by": null },
  "execution": { "event_id": "evt_00042", "action": "reroute_gateway", "channel": "none",
                 "attempted_at": "2026-09-04T10:00:03Z", "outcome": "recovered",
                 "amount_recovered": 4999, "outreach_cost": 0 },
  "audit": [
    { "id": "aud_000101", "ts": "2026-09-04T10:00:01Z", "event_id": "evt_00042",
      "stage": "triage", "actor": "agent", "detail": {} }
  ]
}
```
`customer` here is the **masked** view (no `name`, no `responsiveness`). `404` if unknown id.

---

## GET /graph
Response `200` (`LeakGraph`):
```json
{
  "nodes": [
    { "id": "issuer:ICICI", "label": "ICICI", "kind": "issuer", "value": 410000 },
    { "id": "failure:issuer_downtime", "label": "Issuer downtime", "kind": "failure", "value": 410000 },
    { "id": "loss:total", "label": "Revenue loss", "kind": "loss", "value": 757000 }
  ],
  "edges": [
    { "source": "issuer:ICICI", "target": "failure:issuer_downtime", "rupees": 410000, "label": "" },
    { "source": "failure:issuer_downtime", "target": "loss:total", "rupees": 410000, "label": "33%" }
  ]
}
```

---

## GET /audit
Query (all optional, AND-combined): `?event` · `?stage` · `?actor` · `?outcome` ·
`?limit` (default 200) · `?offset`.

Response `200`:
```json
{ "entries": [
  { "id": "aud_000101", "ts": "2026-09-04T10:00:01Z", "event_id": "evt_00042",
    "stage": "triage", "actor": "agent", "detail": {} }
], "total": 1840 }
```

---

## GET /compliance
Response `200` (`ComplianceReport`):
```json
{
  "counters": { "deferred": 22, "suppressed": 8, "stopped": 14,
                "escalated": 6, "auto_executed": 210, "awaiting_review": 0 },
  "items": [
    { "event_id": "evt_00311", "rule_id": "quiet_hours", "rule_label": "Quiet hours (21:00-09:00 IST)",
      "disposition": "deferred", "detail": { "local_time": "23:14" } }
  ]
}
```

---

## GET /review
Response `200`:
```json
{ "items": [
  { "event_id": "evt_00120", "action": "payment_link_nudge",
    "rationale": "Card expired; a hosted update-card link is the lowest-friction fix.",
    "status": "pending", "decided_by": null, "decided_at": null }
] }
```
Empty `items` in `auto` mode.

## POST /review/{event_id}
Request: `{ "decision": "approved" }`  (`"approved" | "rejected"`)
Response `200`: the updated `review_item` + the resulting `execution` (on approve).
Writes an `audit_entry` with `actor: "human"`. `404` if not queued, `409` if already decided.

---

## POST /chat
Request: `{ "question": "Why is revenue down this week?" }`
Response `200`:
```json
{
  "intent": "why_down",
  "answer": "Revenue is down ~₹7.6L this batch. 54% traces to ICICI issuer downtime ...",
  "grounded_on": ["aggregate:recovered_by_cause", "compliance:counters"]
}
```
`intent` ∈ `why_down` · `customer_detail` · `top_causes` · `unknown`. On LLM failure the
server still returns `200` with a templated `answer` built from aggregates.

---

## POST /admin/reset
Request: `{ "seed": 7 }` · Response `200`: `{ "status": "reseeded", "event_count": 400 }`

---

## Errors
Uniform shape: `{ "error": { "code": "not_found", "message": "unknown event evt_9" } }`
Codes: `not_found` (404) · `conflict` (409) · `validation` (422) · `not_implemented` (501)
· `internal` (500).
