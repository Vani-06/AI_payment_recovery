"""Causal leak graph — Phase 2 (SPEC.md §9 "Leak Graph").

attribute (issuer / gateway / method / region) -> failure mode (cause) -> revenue loss.
Node value = at-risk rupees flowing through it; failure->loss edge weight = unrecovered
rupees, labelled with its share of total loss.
"""

from __future__ import annotations

from collections import defaultdict

from .enums import Cause
from .models import Customer, Diagnosis, Execution, RevenueEvent

# cause -> (attribute kind, how to key it off the event/customer)
_CAUSE_ATTR: dict[str, tuple[str, str]] = {
    Cause.issuer_downtime.value: ("issuer", "issuer"),
    Cause.card_expired.value: ("issuer", "issuer"),
    Cause.gateway_degradation.value: ("gateway", "gateway"),
    Cause.upi_timeout.value: ("region", "region"),
    Cause.checkout_latency.value: ("region", "region"),
    Cause.insufficient_funds_salary_cycle.value: ("method", "method"),
    Cause.mandate_revoked.value: ("method", "method"),
    # price_shock_shipping / forgot_to_pay / disputed / undetermined -> no attribute node
}


def _label(cause: str) -> str:
    return cause.replace("_", " ").capitalize()


def build_leak_graph(
    events: list[RevenueEvent],
    diagnoses: list[Diagnosis],
    executions: list[Execution],
    customers: list[Customer],
    top_n: int = 8,
) -> dict:
    cause_of = {d.event_id: d.cause for d in diagnoses}
    recovered_of = {x.event_id: x.amount_recovered for x in executions}
    region_of = {c.id: c.region for c in customers}

    total_loss = sum(e.amount - recovered_of.get(e.id, 0) for e in events)

    attr_val: dict[tuple[str, str], int] = defaultdict(int)
    fail_val: dict[str, int] = defaultdict(int)
    fail_loss: dict[str, int] = defaultdict(int)
    edge_af: dict[tuple[str, str], int] = defaultdict(int)  # (attr_id, cause) -> at-risk

    for e in events:
        cause = cause_of.get(e.id, Cause.undetermined.value)
        loss = e.amount - recovered_of.get(e.id, 0)
        fail_val[cause] += e.amount
        fail_loss[cause] += loss
        attr = _CAUSE_ATTR.get(cause)
        if not attr:
            continue
        kind, field_name = attr
        key = region_of.get(e.customer_id, "unknown") if field_name == "region" else getattr(e, field_name)
        if not key:
            continue
        attr_val[(kind, key)] += e.amount
        edge_af[(f"{kind}:{key}", cause)] += e.amount

    kept = {f"{k}:{v}" for (k, v), _ in sorted(attr_val.items(), key=lambda kv: -kv[1])[:top_n]}

    nodes: list[dict] = []
    for (kind, key), val in attr_val.items():
        nid = f"{kind}:{key}"
        if nid in kept:
            nodes.append({"id": nid, "label": str(key), "kind": kind, "value": val})
    for cause, val in fail_val.items():
        nodes.append({"id": f"failure:{cause}", "label": _label(cause), "kind": "failure", "value": val})
    nodes.append({"id": "loss:total", "label": "Revenue loss", "kind": "loss", "value": total_loss})

    edges: list[dict] = []
    for (attr_id, cause), val in sorted(edge_af.items(), key=lambda kv: -kv[1]):
        if attr_id in kept:
            edges.append({"source": attr_id, "target": f"failure:{cause}", "rupees": val, "label": ""})
    for cause, loss in sorted(fail_loss.items(), key=lambda kv: -kv[1]):
        pct = round(100 * loss / total_loss) if total_loss else 0
        edges.append({"source": f"failure:{cause}", "target": "loss:total", "rupees": loss, "label": f"{pct}%"})

    return {"nodes": nodes, "edges": edges}
