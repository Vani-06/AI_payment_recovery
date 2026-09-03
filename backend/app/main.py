"""FastAPI entrypoint — Phase 0.

Only ``/health`` is real. ``/results`` serves the committed fixture so the frontend can be
built in parallel. Every other contract endpoint returns 501 until its phase (see
docs/PHASES.md). Handlers get filled in at Phase 3.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .schemas import HealthResponse, ResultsResponse

app = FastAPI(title="Revenue Sherlock", version="0.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_results.json"


def _not_implemented(name: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": f"{name} lands in a later phase"}},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/results", response_model=ResultsResponse)
def results() -> ResultsResponse:
    """P0: return the fixture verbatim. P3: return the persisted last run."""
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return ResultsResponse.model_validate(data)


@app.post("/run")
def run() -> JSONResponse:  # -> RunSummary  (Phase 3)
    return _not_implemented("POST /run")


@app.get("/event/{event_id}")
def event(event_id: str) -> JSONResponse:  # -> EventTrace  (Phase 3)
    return _not_implemented("GET /event/{id}")


@app.get("/graph")
def graph() -> JSONResponse:  # -> LeakGraph  (Phase 3)
    return _not_implemented("GET /graph")


@app.get("/audit")
def audit() -> JSONResponse:  # -> AuditResponse  (Phase 3)
    return _not_implemented("GET /audit")


@app.get("/compliance")
def compliance() -> JSONResponse:  # -> ComplianceReport  (Phase 3)
    return _not_implemented("GET /compliance")


@app.get("/review")
def review_queue() -> JSONResponse:  # -> ReviewQueue  (Phase 3)
    return _not_implemented("GET /review")


@app.post("/review/{event_id}")
def review_decide(event_id: str) -> JSONResponse:  # -> ReviewDecisionResponse  (Phase 3)
    return _not_implemented("POST /review/{event_id}")


@app.post("/chat")
def chat() -> JSONResponse:  # -> ChatResponse  (Phase 4)
    return _not_implemented("POST /chat")


@app.post("/admin/reset")
def admin_reset() -> JSONResponse:  # -> ResetResponse  (Phase 3)
    return _not_implemented("POST /admin/reset")
