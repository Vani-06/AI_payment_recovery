"""FastAPI entrypoint — Phase 3.

Every contract endpoint is live and reads from Postgres. On first request (no batch run
yet) the demo batch is run lazily so the API always has data.
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from . import chat, queries, review
from .config import settings
from .errors import install as install_errors
from .pipeline import run_batch
from .schemas import (
    AuditResponse,
    ChatRequest,
    ChatResponse,
    ComplianceReport,
    EventTrace,
    HealthResponse,
    LeakGraph,
    ResetRequest,
    ResetResponse,
    ResultsResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewQueue,
    RunInfo,
    RunRequest,
    RunSummary,
)
from .schemas import BatchAggregates

app = FastAPI(title="Revenue Sherlock", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)
install_errors(app)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(phase="3")


@app.post("/run", response_model=RunSummary)
def run(req: RunRequest) -> RunSummary:
    r = run_batch(req.seed, req.mode.value, req.baseline, persist=True)
    return RunSummary(run=RunInfo(**r["run"]), aggregates=BatchAggregates.model_validate(r["aggregates"]))


@app.get("/results", response_model=ResultsResponse)
def results(
    limit: int = 400,
    offset: int = 0,
    outcome: str | None = None,
    cause: str | None = None,
) -> ResultsResponse:
    queries.ensure_batch()
    return queries.build_results(limit=limit, offset=offset, outcome=outcome, cause=cause)


@app.get("/event/{event_id}", response_model=EventTrace)
def event(event_id: str) -> EventTrace:
    queries.ensure_batch()
    return queries.build_event_trace(event_id)


@app.get("/graph", response_model=LeakGraph)
def graph() -> LeakGraph:
    queries.ensure_batch()
    return queries.build_graph()


@app.get("/audit", response_model=AuditResponse)
def audit(
    event: str | None = None,
    stage: str | None = None,
    actor: str | None = None,
    outcome: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> AuditResponse:
    queries.ensure_batch()
    return queries.build_audit(event=event, stage=stage, actor=actor, outcome=outcome, limit=limit, offset=offset)


@app.get("/compliance", response_model=ComplianceReport)
def compliance() -> ComplianceReport:
    queries.ensure_batch()
    return queries.build_compliance()


@app.get("/review", response_model=ReviewQueue)
def review_list() -> ReviewQueue:
    queries.ensure_batch()
    return queries.review_queue()


@app.post("/review/{event_id}", response_model=ReviewDecisionResponse)
def review_decide(event_id: str, req: ReviewDecisionRequest) -> ReviewDecisionResponse:
    return review.apply_decision(event_id, req.decision.value)


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    queries.ensure_batch()
    return chat.answer(req.question)


@app.post("/admin/reset", response_model=ResetResponse)
def admin_reset(req: ResetRequest) -> ResetResponse:
    r = run_batch(req.seed, "auto", persist=True)
    return ResetResponse(status="reseeded", event_count=r["run"]["event_count"])
