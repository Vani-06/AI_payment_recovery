"""Grounded Q&A over the current batch — Phase 3 (templated).

Three intents, answered from the stored ``batch_run`` aggregates + leak graph + audit
log. Phase 4 swaps the templated bodies for LLM-written prose over the same grounding.
"""

from __future__ import annotations

import re

from sqlmodel import Session, select

from .db import ENGINE
from .errors import ApiError
from .llm import LLMError, llm, llm_available
from .models import BatchRun, Customer, Diagnosis, Execution, RevenueEvent
from .schemas import ChatResponse

_CUS_RE = re.compile(r"(cus_\d{1,4}|customer\s*#?\s*\d{1,4})", re.I)

_CHAT_SYS = (
    "You are a revenue-operations analyst answering a colleague. Rewrite the given facts "
    "as a direct 2-4 sentence answer to the question. Use ONLY the facts provided — never "
    "invent or round numbers differently. Plain text, no markdown."
)


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _resp(intent: str, facts: str, grounded: list[str], question: str) -> ChatResponse:
    """Templated `facts` are the ground truth; the LLM only rephrases them if available."""
    answer = facts
    if llm_available():
        try:
            answer = llm(_CHAT_SYS, f"Question: {question}\n\nFacts:\n{facts}", max_tokens=220)
        except LLMError:
            pass
    return ChatResponse(intent=intent, answer=answer, grounded_on=grounded)


def answer(question: str) -> ChatResponse:
    q = question.lower().strip()
    with Session(ENGINE) as s:
        run = s.exec(select(BatchRun).order_by(BatchRun.id.desc())).first()
        if run is None:
            raise ApiError("not_found", 404, "no batch has been run yet")
        agg = run.aggregates
        graph = run.leak_graph

        m = _CUS_RE.search(q)
        if m and ("customer" in q or "cus_" in q):
            return _customer_detail(s, m.group(0), question)

    if any(w in q for w in ("why", "down", "drop", "leak", "losing", "lose", "falling")):
        loss_edges = sorted(
            (e for e in graph["edges"] if e["target"] == "loss:total"),
            key=lambda e: -e["rupees"],
        )[:3]
        parts = ", ".join(
            f"{e['source'].split(':', 1)[1].replace('_', ' ')} ({e['label']} of loss)" for e in loss_edges
        )
        body = (
            f"Revenue at risk this batch is Rs {agg['revenue_at_risk']:,}. "
            f"The largest leak sources are {parts}. "
            f"The agent recovered Rs {agg['revenue_recovered']:,} ({_pct(agg['recovery_rate'])}) "
            f"versus {_pct(agg['baseline_recovery_rate'])} for naive retry-everything. "
            f"It held off on {agg['compliance']['escalated']} disputed/on-hold accounts and "
            f"deferred {agg['compliance']['deferred']} for quiet hours or promise-to-pay."
        )
        return _resp("why_down", body, ["batch_run.leak_graph", "batch_run.aggregates"], question)

    if "cause" in q or "top" in q:
        top = agg["recovered_by_cause"][:4]
        lines = "; ".join(
            f"{r['cause'].replace('_', ' ')} Rs {r['recovered']:,}/{r['at_risk']:,} "
            f"({_pct(r['recovered'] / r['at_risk']) if r['at_risk'] else '0%'})"
            for r in top
        )
        return _resp("top_causes", f"Top loss causes by revenue at risk: {lines}.", ["batch_run.aggregates.recovered_by_cause"], question)

    return ChatResponse(
        intent="unknown",
        answer="I can tell you why revenue is down this batch, the top loss causes, or what happened for a specific customer (e.g. 'what did you do for cus_0117?').",
        grounded_on=[],
    )


def _customer_detail(s: Session, token: str, question: str) -> ChatResponse:
    digits = re.sub(r"\D", "", token)
    cid = f"cus_{int(digits):04d}"
    cust = s.get(Customer, cid)
    if cust is None:
        raise ApiError("not_found", 404, f"unknown customer {cid}")

    events = s.exec(select(RevenueEvent).where(RevenueEvent.customer_id == cid)).all()
    if not events:
        return ChatResponse(intent="customer_detail", answer=f"{cust.label} had no at-risk events this batch.", grounded_on=[])

    ids = [e.id for e in events]
    execs = {x.event_id: x for x in s.exec(select(Execution).where(Execution.event_id.in_(ids))).all()}
    diags = {d.event_id: d for d in s.exec(select(Diagnosis).where(Diagnosis.event_id.in_(ids))).all()}

    lines = []
    recovered = 0
    for e in events:
        x = execs.get(e.id)
        d = diags.get(e.id)
        recovered += x.amount_recovered if x else 0
        lines.append(
            f"{e.id} ({e.type}, Rs {e.amount:,}): diagnosed {d.cause if d else '?'} -> "
            f"{x.action if x else '?'} -> {x.outcome if x else '?'}"
            + (f" (recovered Rs {x.amount_recovered:,})" if x and x.amount_recovered else "")
        )
    flags = [f for f, v in (("DND", cust.dnd), ("opt-out", cust.opt_out), ("on hold", cust.on_hold)) if v]
    flag_txt = f" Flags: {', '.join(flags)}." if flags else ""
    facts = (
        f"{cust.label} ({cust.segment}, {cust.region}){flag_txt} "
        f"{len(events)} at-risk event(s), Rs {recovered:,} recovered. " + " | ".join(lines)
    )
    return _resp("customer_detail", facts, [f"revenue_event[{cid}]", "execution", "diagnosis"], question)
