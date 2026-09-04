"""Diagnosis narratives + plan rationales — Phase 4.

The LLM only ever *explains* — it is handed the cause and the action and must not change
them. Results are cached to disk keyed by content hash, so repeat runs (and demos) are
instant and stable, and a missing API key just yields templated prose.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from .llm import LLMError, llm

_CACHE_PATH = Path(__file__).resolve().parents[1] / ".cache" / "narratives.json"
_LOCK = threading.Lock()


def _load() -> dict[str, str]:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


_CACHE: dict[str, str] = _load()


def _key(*parts: object) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:20]


def _cached(key: str, produce) -> str:
    if key in _CACHE:
        return _CACHE[key]
    value = produce()
    with _LOCK:
        _CACHE[key] = value
        _CACHE_PATH.parent.mkdir(exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(_CACHE, indent=0), encoding="utf-8")
    return value


_DIAG_SYS = (
    "You are a payments revenue-operations analyst. You are GIVEN the root cause of a "
    "failed transaction and the statistics it was derived from. Do NOT dispute or change "
    "the cause. In 2-3 plain sentences, explain to an ops colleague why this cause is the "
    "likely explanation, citing the specific numbers provided. No preamble, no markdown, "
    "no bullet points."
)

_PLAN_SYS = (
    "You are a revenue-recovery agent explaining your chosen action to an operator. Given "
    "the diagnosed cause, the action, the channel and basic customer context, write ONE "
    "short paragraph (2-3 sentences) on why this action fits the cause and how the "
    "customer state shaped it. Plain text, no markdown."
)


def _humanize(s: str) -> str:
    return s.replace("_", " ")


# ------------------------------------------------------------------------------------
# Diagnosis narrative
# ------------------------------------------------------------------------------------


def _diag_template(cause: str, confidence: float, evidence: dict) -> str:
    bits: list[str] = []
    ev = evidence or {}
    if "issuer" in ev:
        bits.append(f"issuer {ev['issuer']} is over-represented (lift {ev.get('issuer_lift', '?')})")
    if "gateway" in ev:
        bits.append(f"gateway {ev['gateway']} is over-represented (lift {ev.get('gateway_lift', '?')})")
    if ev.get("window_share") is not None:
        bits.append(f"{ev['window_share']} of failures in a tight time window over {ev.get('window_events', '?')} events")
    if ev.get("android"):
        bits.append(f"Android + UPI concentration in {ev.get('region', 'a region')}")
    if "latency_ms" in ev:
        bits.append(f"checkout latency {ev['latency_ms']}ms")
    if "shipping_fee" in ev:
        bits.append(f"shipping fee {ev['shipping_fee']} ({ev.get('shipping_ratio', '?')} of cart)")
    if ev.get("error_code") or ev.get("decline_code"):
        bits.append(f"gateway signalled '{ev.get('error_code') or ev.get('decline_code')}'")
    if ev.get("day") or ev.get("day_of_month"):
        bits.append("failure fell in the first days of the month")
    if ev.get("days_overdue") is not None:
        bits.append(f"invoice {ev['days_overdue']} days overdue")
    reason = "; ".join(bits) if bits else "the available signals point this way"
    gated = " (below the confidence threshold, so treated conservatively)" if cause == "undetermined" else ""
    return f"Diagnosed as {_humanize(cause)} (confidence {confidence:.2f}){gated}. Evidence: {reason}."


def diagnosis_narrative(event: dict, cause: str, confidence: float, evidence: dict) -> str:
    key = _key("diag", cause, round(confidence, 2), json.dumps(evidence, sort_keys=True))

    def produce() -> str:
        prompt = (
            f"Transaction: {event.get('type')} of Rs {event.get('amount')} on {event.get('gateway')} "
            f"via {event.get('method')} (issuer {event.get('issuer')}).\n"
            f"Given root cause: {cause}\nConfidence: {confidence:.2f}\n"
            f"Statistics it was derived from: {json.dumps(evidence)}"
        )
        try:
            return llm(_DIAG_SYS, prompt, max_tokens=200)
        except LLMError:
            return _diag_template(cause, confidence, evidence)

    return _cached(key, produce)


# ------------------------------------------------------------------------------------
# Plan rationale
# ------------------------------------------------------------------------------------

_ACTION_REASON = {
    "reroute_gateway": "reroute new attempts around the failing gateway",
    "smart_retry": "retry on a schedule tuned to transient failures",
    "retry_on_payday": "retry when the customer's balance is likely restored",
    "update_card_link": "send a hosted link to refresh the expired instrument",
    "payment_link_nudge": "send a low-friction payment link",
    "coupon_offer": "offset the price shock with a capped incentive",
    "dunning_email": "run the standard reminder sequence",
    "finance_escalation": "hand the receivable to finance for direct follow-up",
    "no_action_stop": "hold — no action clears the stopping rules or the economics",
}


def _plan_template(cause: str, action: str, channel: str, customer: dict, amount: int) -> str:
    base = _ACTION_REASON.get(action, "apply the mapped intervention")
    state = []
    if customer.get("on_hold"):
        state.append("account is on manual hold")
    if customer.get("promise_to_pay_date"):
        state.append("a promise-to-pay is on file")
    if customer.get("dnd") or customer.get("opt_out"):
        state.append("customer has opted out of outreach")
    ctx = f" Customer state: {', '.join(state)}." if state else ""
    ch = "" if channel == "none" else f" via {channel}"
    return (
        f"Cause is {_humanize(cause)}, so the plan is to {base}{ch}. "
        f"On a Rs {amount:,} {customer.get('segment', 'b2c')} account this is the "
        f"lowest-friction step that targets the cause rather than the customer.{ctx}"
    )


def plan_rationale(cause: str, action: str, channel: str, customer: dict, amount: int) -> str:
    key = _key("plan", cause, action, channel, customer.get("segment"), amount // 1000, bool(customer.get("on_hold")), bool(customer.get("promise_to_pay_date")))

    def produce() -> str:
        prompt = (
            f"Diagnosed cause: {cause}\nChosen action: {action}\nChannel: {channel}\n"
            f"Amount at risk: Rs {amount}\n"
            f"Customer: segment {customer.get('segment')}, region {customer.get('region')}, "
            f"on_hold={customer.get('on_hold')}, promise_to_pay={bool(customer.get('promise_to_pay_date'))}, "
            f"dnd={customer.get('dnd')}, opt_out={customer.get('opt_out')}"
        )
        try:
            return llm(_PLAN_SYS, prompt, max_tokens=180)
        except LLMError:
            return _plan_template(cause, action, channel, customer, amount)

    return _cached(key, produce)


def warm_narratives() -> int:
    """Pre-fill narrative + rationale for every event in the current batch (demo warming)."""
    from sqlmodel import Session, select

    from .db import ENGINE
    from .models import Customer, Diagnosis, Execution, Plan, RevenueEvent
    from .schemas import CustomerMasked, EventPublic

    n = 0
    with Session(ENGINE) as s:
        events = s.exec(select(RevenueEvent)).all()
        custs = {c.id: c for c in s.exec(select(Customer)).all()}
        for e in events:
            d = s.get(Diagnosis, e.id)
            p = s.get(Plan, e.id)
            if d and not d.narrative:
                d.narrative = diagnosis_narrative(EventPublic.of(e).model_dump(), d.cause, d.confidence, d.evidence)
                s.add(d)
                n += 1
            if p and not p.rationale:
                p.rationale = plan_rationale(
                    d.cause if d else "undetermined",
                    p.action,
                    p.channel,
                    CustomerMasked.of(custs[e.customer_id]).model_dump(mode="json"),
                    e.amount,
                )
                s.add(p)
        s.commit()
    return n
