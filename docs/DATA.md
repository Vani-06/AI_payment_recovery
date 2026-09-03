# Data Model & Enums (frozen — Phase 0)

Runtime source of truth: `backend/app/enums.py` + `backend/app/schemas.py`.
TS mirror: `frontend/lib/types.ts`. **Change all three together.**

Money: all amounts are **whole Indian rupees (INR)** as integers. `₹12.4L` in the UI =
`1_240_000` on the wire. No paise, no floats for money.

Timestamps: ISO-8601 UTC strings (`2026-09-04T10:00:00Z`).

IDs: string, prefixed — `cus_0001`, `evt_00001`, `aud_000001`.

---

## Enums

### EventType
`payment_failed` · `checkout_abandoned` · `invoice_overdue` · `subscription_failed`

### Cause
`card_expired` · `insufficient_funds_salary_cycle` · `issuer_downtime` ·
`gateway_degradation` · `upi_timeout` · `checkout_latency` · `price_shock_shipping` ·
`mandate_revoked` · `forgot_to_pay` · `disputed` · `undetermined`

`undetermined` is only ever produced by confidence gating (SPEC §16), never seeded as a
`true_cause`.

### Action
`smart_retry` · `retry_on_payday` · `reroute_gateway` · `update_card_link` ·
`payment_link_nudge` · `dunning_email` · `coupon_offer` · `finance_escalation` ·
`no_action_stop`

Silent (no customer contact): `smart_retry`, `retry_on_payday`, `reroute_gateway`,
`no_action_stop`. Everything else is outreach and passes the outreach compliance rules.

### Channel
`whatsapp` · `email` · `sms` · `voice` · `finance_touch` · `none`

### Outcome
`recovered` · `partial` · `failed` · `deferred` · `suppressed` · `awaiting_review`

### Stage
`triage` · `root_cause` · `plan` · `compliance` · `execute` · `audit`

### Actor  (audit entry author)
`agent` · `compliance` · `system` · `human`

### Mode
`auto` · `review`

### Segment
`b2c` · `b2b`

### ComplianceRuleId  (SPEC §8)
`contact_cap` · `channel_cooldown` · `quiet_hours` · `dnd_optout` · `promise_to_pay_hold` ·
`manual_hold_dispute` · `discount_guardrail` · `economic_stop` · `global_batch_cap` ·
`review_mode_gate`

### ComplianceDisposition
`passed` · `blocked` · `deferred` · `awaiting_review`

### ReviewStatus
`pending` · `approved` · `rejected`

### LeakNodeKind
`gateway` · `issuer` · `method` · `region` · `failure` · `loss`

---

## Tables

### customer
| field | type | notes |
|---|---|---|
| id | str | `cus_0001` |
| label | str | masked display name, `Customer #1` — the only name the model/audit ever see |
| name | str | real name, **local/UI only**, never sent to the model or written to audit |
| segment | Segment | |
| region | str | e.g. `south`, `west`, `north`, `east` |
| method_pref | str | `upi` \| `card` \| `netbanking` \| `wallet` |
| dnd | bool | |
| opt_out | bool | |
| contact_count_7d | int | rolling; mutated by compliance during a run |
| last_contacted_at | str \| null | |
| promise_to_pay_date | str \| null | |
| on_hold | bool | manual hold |
| responsiveness | float 0..1 | **hidden**; feeds the outcome engine only |

### revenue_event
| field | type | notes |
|---|---|---|
| id | str | `evt_00001` |
| type | EventType | |
| customer_id | str | |
| amount | int (INR) | revenue at risk for this event |
| currency | str | always `INR` for the demo |
| created_at | str | |
| gateway | str | `razorpay_pg_a` \| `razorpay_pg_b` \| ... |
| method | str | `upi` \| `card` \| `netbanking` \| `wallet` |
| issuer | str | bank / network, e.g. `ICICI`, `HDFC`, `Visa` |
| bin | str | first 6 digits, card only, else `null` |
| status | str | raw event status, e.g. `failed`, `abandoned`, `overdue` |
| true_cause | Cause | **hidden**; ground truth for the outcome engine |
| meta | object | free-form (device, attempt_no, latency_ms, ...) |

### diagnosis
| field | type | notes |
|---|---|---|
| event_id | str | |
| cause | Cause | chosen by **deterministic analytics**, not the LLM |
| confidence | float 0..1 | |
| evidence | object | the cross-batch stats the cause was derived from |
| narrative | str | LLM-written explanation (empty until Phase 4) |

### plan
| field | type | notes |
|---|---|---|
| event_id | str | |
| action | Action | from the policy table |
| channel | Channel | `none` for silent actions |
| rationale | str | LLM-written (empty until Phase 4) |
| blocked_by | ComplianceRuleId \| null | set if compliance blocked/deferred it |

### execution
| field | type | notes |
|---|---|---|
| event_id | str | |
| action | Action | as executed (may be `no_action_stop` after a block) |
| channel | Channel | |
| attempted_at | str | |
| outcome | Outcome | |
| amount_recovered | int (INR) | full on `recovered`, seeded fraction on `partial`, else 0 |
| outreach_cost | int (INR) | channel unit cost if an outreach was sent, else 0 |

### review_item   (Review Mode only)
| field | type | notes |
|---|---|---|
| event_id | str | |
| action | Action | |
| rationale | str | |
| status | ReviewStatus | |
| decided_by | str \| null | |
| decided_at | str \| null | |

### audit_entry   (append-only — no update/delete path in code)
| field | type | notes |
|---|---|---|
| id | str | `aud_000001` |
| ts | str | |
| event_id | str | |
| stage | Stage | |
| actor | Actor | |
| detail | object | stage-specific; diagnosis entries embed the `evidence` stats |

---

## Derived / response-only shapes

### EventRow  (Batch Run table)
`event_id, customer_id, customer_label, type, amount, cause, confidence, action,
compliance_status (ComplianceDisposition), blocked_by, outcome, amount_recovered`

### EventTrace  (`GET /event/{id}`)
`event, customer (masked), triage, diagnosis, plan, execution, audit[]`

### BatchAggregates
`revenue_at_risk, revenue_recovered, recovery_rate, baseline_recovery_rate, outreach_cost,
net_recovery, cost_per_rupee_recovered, audit_coverage,
recovered_by_cause[] {cause, at_risk, recovered},
compliance {deferred, suppressed, stopped, escalated, auto_executed, awaiting_review}`

### LeakGraph
`nodes[] {id, label, kind (LeakNodeKind), value}` · `edges[] {source, target, rupees, label}`

### ComplianceReport
`counters {...same keys as aggregates.compliance...}` ·
`items[] {event_id, rule_id, rule_label, disposition, detail}`
