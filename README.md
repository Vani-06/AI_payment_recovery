# Revenue Sherlock

Bounded revenue-recovery agent for the Razorpay **AI Revenue Recovery** track.
It runs a batch of at-risk revenue events through a **detect -> diagnose -> plan -> execute ->
audit** loop, routes each intervention by **root cause**, enforces compliance / stopping
rules, and reports **measured rupees recovered** with a full audit trail.

- Product + scoring rationale: [docs/SPEC.md](docs/SPEC.md)
- Build plan: [docs/PHASES.md](docs/PHASES.md)
- API contract: [docs/CONTRACT.md](docs/CONTRACT.md)
- Data model + enums: [docs/DATA.md](docs/DATA.md)

## Layout

```
backend/            FastAPI + domain pipeline (Python 3.14)
frontend/           Next.js App Router + Tailwind + Framer Motion
docs/               spec, phases, contract, data model
fixtures/           sample_results.json - example /results payload for FE dev
docker-compose.yml  local Postgres 16
```

## Run - database

```bash
docker compose up -d
```

Postgres 16 on `localhost:5432` (db / user / pass all `sherlock`). Override with
`DATABASE_URL` to use a hosted DB.

## Run - backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.seed --seed 7 --report   # reset + populate Postgres, print sanity check
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health` -> `{"status":"ok"}`
Tests: `cd backend && pytest`

## Run - frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Opens `http://localhost:3000`. Set `NEXT_PUBLIC_API_BASE` in `frontend/.env.local`
(defaults to `http://localhost:8000`).

## Env vars

| Var | Where | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | backend `.env` | `postgresql+psycopg://sherlock:sherlock@localhost:5433/sherlock` | Postgres connection |
| `ANTHROPIC_API_KEY` | backend `.env` | - | LLM calls (Phase 4). Unset => templated fallbacks. |
| `SHERLOCK_MODEL` | backend `.env` | `claude-sonnet-5` | model id behind `llm()` |
| `FRONTEND_ORIGIN` | backend `.env` | `http://localhost:3000` | CORS allow-origin |
| `NEXT_PUBLIC_API_BASE` | frontend `.env.local` | `http://localhost:8000` | API base URL |

## Status

Phase 5 complete: Next.js app shell — left icon rail (7 routes), floating action bar
(seed · agent/baseline · Auto/Review · run), typed API client, Framer Motion baseline
(shared spring, `prefers-reduced-motion` fallback, staggered lists). Command Center shows
live headline metrics; the other six screens render their data in Phases 6-7.
See [docs/PHASES.md](docs/PHASES.md).

Backend (Phases 0-4) is feature-complete: `python -m app.pipeline --seed 7 --narrate`
for the CLI, `uvicorn app.main:app` for the API.
