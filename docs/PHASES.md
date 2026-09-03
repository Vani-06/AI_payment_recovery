# Build Phases — Revenue Sherlock

Execution plan for [SPEC.md](SPEC.md). 10 phases across ~3 days. Each phase has an **exit
criterion** — do not start the next phase until it is met. Two-person split shown as
**[BE]** (backend/domain) and **[FE]** (frontend); solo builder runs them top-to-bottom.

Critical path: **P0 → P1 → P2 → P3 → P4**. Frontend (P5→P8) starts right after P0 against
the frozen contract and mock data, in parallel with BE.

---

## Phase 0 — Setup & contracts  *(~2h, blocking, do together)*

Goal: freeze the interfaces both sides build against so P1–P8 never block each other.

- [ ] Repo scaffold: `/backend` (FastAPI), `/frontend` (Next.js App Router), `/docs`.
- [ ] `docs/CONTRACT.md`: every API endpoint with request/response JSON shape (see P3 list).
- [ ] `docs/DATA.md`: final field list for all tables + the cause enum + action enum + the
      outcome enum (copy from SPEC §6, lock exact names).
- [ ] `backend/app/schemas.py`: Pydantic models for every entity + API payload. This file
      is the contract in code.
- [ ] `frontend/lib/types.ts`: TS mirror of the same shapes (hand-written or generated).
- [ ] `frontend/tailwind.config.ts`: palette tokens from SPEC §9.5.
- [ ] One committed `fixtures/sample_results.json` — a hand-written example `/results`
      payload FE can build against before the backend runs.
- [ ] `README.md`: how to run both (`uvicorn`, `pnpm dev`), ports, env var names.

**Exit:** both apps start, `GET /health` returns 200, FE renders a page reading
`sample_results.json`. Contract files committed.

---

## Phase 1 — Domain core: data + outcome engine  *(~4h, [BE])*

Goal: deterministic world with numbers, no pipeline yet.

- [ ] SQLModel models + SQLite init + `reset_db()`.
- [ ] Seed generator: ~400 `revenue_event`s + ~180 `customer`s across the 4 event types,
      each with a hidden `true_cause` and per-customer `responsiveness`. Seedable RNG.
- [ ] Realistic skews baked in so attribution has something to find: one issuer with a
      failure spike, one gateway degraded in a time window, UPI-timeout cluster in one
      region+method, a batch of card-expiry, a set of overdue invoices with promise-to-pay.
- [ ] Outcome engine: `base[action][cause]` matrix + `recovery_probability()` +
      seeded `draw_outcome(event, action)` → `(outcome, amount_recovered, outreach_cost)`.
- [ ] Unit check: run seed twice with same seed → identical rows; `retry-everything`
      baseline recovers visibly less than a hand-picked "correct action per cause" pass.

**Exit:** `python -m backend.seed --seed 7` populates the DB; a throwaway script prints
₹-at-risk and a baseline vs oracle recovery number.

---

## Phase 2 — Pipeline + compliance + audit  *(~5h, [BE])*

Goal: full detect→diagnose→plan→execute→audit loop with stubbed narratives.

- [ ] `stage_triage(event)` → type, expected_loss, recoverability, priority.
- [ ] `stage_root_cause(event, batch_stats)` → cause + confidence + evidence dict, using
      **real cross-batch analytics** (issuer failure rate vs baseline, method/region/gateway
      skew, time clustering). Narrative = `""` for now.
- [ ] `compute_batch_stats(events)` — the aggregates root-cause reads. Run once per batch.
- [ ] `stage_plan(event, diagnosis, customer)` → action from the policy table; rationale `""`.
- [ ] `compliance_check(plan, customer, batch_counters)` → pass / `blocked_by(rule_id)` /
      `awaiting_review`. All 10 rules from SPEC §8. Mutates contact counters.
- [ ] `stage_execute(event, plan)` → calls outcome engine; writes `execution`.
- [ ] `stage_audit(...)` — append `audit_entry` after every stage. Append-only helper; no
      update path anywhere.
- [ ] `run_batch(seed, mode, baseline=False)` orchestrates all of it + returns aggregates
      (₹ at risk, ₹ recovered, rate, net, by-cause, compliance counters, audit coverage).
- [ ] `build_leak_graph(events, diagnoses)` → nodes + weighted edges for React Flow.

**Exit:** `run_batch()` returns a complete aggregates object; compliance counters are
non-zero; audit coverage = 100%; baseline mode returns a lower rate.

---

## Phase 3 — Backend API  *(~3h, [BE])*

Goal: expose the pipeline over HTTP per the frozen contract.

- [ ] `POST /run` `{seed, mode, baseline}` → runs batch, persists, returns run summary.
- [ ] `GET /results` → aggregates + per-event rows (paged/limited).
- [ ] `GET /event/{id}` → full stage trace (triage, diagnosis+evidence, plan+rationale,
      execution, audit entries).
- [ ] `GET /graph` → leak-graph nodes + edges.
- [ ] `GET /audit` `?event&stage&actor&outcome` → filtered append-only log.
- [ ] `GET /compliance` → counters + list of blocked/deferred/stopped with reasons.
- [ ] `GET /review` / `POST /review/{event_id}` `{decision}` → queue + approve/reject,
      writes `audit_entry` with `actor: human`, executes on approve.
- [ ] `POST /chat` `{question}` → (stub → real in P4) grounded answer.
- [ ] CORS for the FE origin; seed/reset endpoint for demos.

**Exit:** every endpoint returns contract-shaped JSON; FE `sample_results.json` can be
deleted and the real `/results` renders the same.

---

## Phase 4 — LLM integration  *(~3h, [BE])*

Goal: real intelligence layer, behind one swappable function.

- [ ] `llm(system, prompt, schema=None)` — single entry point, provider configurable
      (`claude-sonnet-5` primary, adaptive thinking, low–medium effort).
- [ ] Diagnosis narrative: feed the computed evidence stats → 2–3 sentence explanation.
      **Model never chooses the cause** — asserts this in the system prompt and in code
      (cause is passed in, not returned).
- [ ] Plan rationale: cause + action + customer state → one-paragraph "why this action".
- [ ] Confidence gating: diagnosis confidence < threshold → cause `undetermined` →
      conservative action only.
- [ ] `/chat`: 3 intents (why revenue down / what happened for customer X / top causes),
      answered from batch aggregates + audit log stuffed into context. Templated fallback
      if the call fails.
- [ ] Cache diagnoses to disk keyed by `(seed, event_id)` so demo runs are instant.

**Exit:** an event drawer shows a written diagnosis + rationale; chat answers the 3
intents with correct numbers; disabling the network falls back to templates without error.

---

## Phase 5 — Frontend shell  *(~4h, [FE], starts after P0)*

Goal: the app frame, navigation, motion baseline, API client.

- [ ] Layout: left icon rail (7 destinations) + main canvas + **floating action bar**
      (seed selector · baseline toggle · Auto/Review switch · circular primary button).
- [ ] Routing for all 7 screens (empty states for now).
- [ ] `lib/api.ts` typed client for every endpoint.
- [ ] Tailwind tokens wired; base card component (squircle, soft shadow), blob accent
      component, tabular-nums number component.
- [ ] Framer Motion set up: shared spring preset, `prefers-reduced-motion` hook,
      staggered-list wrapper.

**Exit:** all 7 routes reachable; action bar visible; one demo card animates in with the
spring; reduced-motion disables travel.

---

## Phase 6 — Core screens  *(~5h, [FE])*

- [ ] **Command Center**: ₹ at risk · recovered · rate · net recovery · audit coverage ·
      recovered-by-cause bar (Recharts) · baseline delta. Count-up on run complete.
- [ ] **Batch Run**: table (event, customer, type, ₹, cause+confidence, action, compliance
      status, outcome, ₹ recovered), outcome-colored. Row → **right drawer** with the full
      stage trace, revealed stage-by-stage.
- [ ] **Audit Trail**: filterable log view (event / stage / actor / outcome).
- [ ] Wire **Run batch** → `POST /run` → refresh all three.

**Exit:** click Run batch → numbers animate up, table fills with colored outcomes, a row
drawer shows a real trace, audit filters work.

---

## Phase 7 — Signature screens  *(~5h, [FE])*

- [ ] **Leak Graph** (React Flow): weighted nodes/edges from `/graph`, animated dashed
      edge-flow, width ∝ ₹, spring layout settle. Pre-computed layout fallback ready.
- [ ] **Compliance panel**: deferred / suppressed / stopped / escalated counters + the
      reason list. Reads `/compliance`.
- [ ] **Review queue**: pending items with diagnosis + rationale, Approve / Reject →
      `POST /review/{id}`, optimistic update, toast. Empty in Auto Mode.
- [ ] **Chat**: input + message list, 3 suggested prompts, grounded answers from `/chat`.

**Exit:** Leak Graph tells the "68% from two causes" story at a glance; Review Mode flip
routes outreach into the queue and Approve executes it.

---

## Phase 8 — Motion & polish  *(~4h, [FE])*

- [ ] **Run-batch card flow**: event cards travel through the 5 stage columns and land in
      outcome color. This is the headline animation.
- [ ] **Replay as stream**: same, one card every ~120ms, throttled.
- [ ] Count-up timing, edge-flow speed, drawer spring — tuned to feel calm, not busy.
- [ ] Loading skeletons, empty states, error toasts on every screen.
- [ ] Pointer parallax on Command Center hero tiles; verify all motion respects
      reduced-motion.
- [ ] Responsive down to a laptop screen (1280px); no horizontal scroll.

**Exit:** a cold run looks like the SPEC §13 demo without narration; nothing janky.

---

## Phase 9 — Tuning & demo hardening  *(~3h, together)*

- [ ] Tune `base[action][cause]` so batch recovery lands ~35–45% and baseline ~22–26%.
- [ ] Lock a demo seed; pre-run + cache it so "Run batch" is instant on stage.
- [ ] Walk SPEC §13 script end to end 3×; fix whatever stalls.
- [ ] **Record a full fallback screen-capture** with voiceover.
- [ ] `docs/DEMO.md`: exact click order, the seed, the talking points, the numbers to say.
- [ ] One-command local start (`make dev` or a script); confirm on a clean checkout.

**Exit:** demo runs identically twice in a row from a clean start; fallback video exists.

---

## If behind — cut in this order

1. Pointer parallax + fancy edge-flow → static.
2. Chat → 3 hard-templated answers from aggregates (drop the LLM call).
3. Replay-as-stream → keep only the one-shot card flow.
4. Review queue UI → keep the mode toggle + counter, skip the approve interaction.
5. Audit Trail filters → single unfiltered list.

**Never cut:** the hero metric + baseline comparison, the per-event stage trace, the
compliance counters, the Leak Graph. Those are the four things judges score.

---

## Rough day mapping

| Day | Phases |
|---|---|
| 1 | P0, P1, P2 · FE starts P5 |
| 2 | P3, P4 · FE P6, start P7 |
| 3 | FE P7 finish, P8 · P9 together |
