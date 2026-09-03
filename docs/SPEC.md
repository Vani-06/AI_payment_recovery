# Build Spec — "Revenue Sherlock"

Razorpay track: **AI Revenue Recovery**. 3-day hackathon build. This doc is the source of
truth for scope, architecture, and the demo. Read it before writing code.

---

## 1. The verdict (what we are building)

**Revenue Sherlock** — an agent that runs a **bounded recovery workflow over a batch of
at-risk revenue events**, and for every rupee it touches produces a **root-cause diagnosis,
a compliant action, and an audit receipt**.

One line: *"Don't just chase the payment. Explain why it broke, fix the cause, and prove
how much you got back."*

The differentiator is **root-cause attribution feeding a bounded, compliant execution loop
with measured recovery** — not prediction, not another reminder bot.

---

## 2. Scraping the existing ideas — keep / cut

The brainstorm produced four framings (RevenueDNA, Revenue Twin, Revenue Sherlock,
Revenue Leak Investigator). They are 80% the same system. Decisions:

| Idea element | Decision | Why |
|---|---|---|
| **Root-cause attribution** ("12% drop = 68% ICICI UPI, 21% shipping, 11% churn") | **KEEP — this is the spine** | Demoable, differentiated, and it's what a payments company actually wants. |
| **Causal leak graph** (React Flow: cause → effect → ₹ loss) | **KEEP — hero visual** | Nobody in the recovery market shows this well. Sells the "intelligence" claim in one screen. |
| **Bounded recovery loop** (detect → diagnose → plan → execute → audit over a batch) | **KEEP — this is what the rubric scores** | Track's "THE BAR" is literally: measured money recovered, compliant escalation, stopping rules, audit trail. |
| **Compliance + stopping rules engine** | **KEEP — promote to a first-class module** | Biggest rubric point most teams will skip. Cheap to build, huge credibility. |
| **Audit trail** | **KEEP — required** | Append-only log, filterable in UI. |
| **"Chat with your revenue data"** | **KEEP — but thin** | One RAG-lite endpoint over the batch + audit log. Great closing demo beat. Do NOT build a full analytics chatbot. |
| **Prediction** ("where will revenue leak next week", Revenue Twin simulation) | **CUT to a static flag** | Cannot show real accuracy in 3 days. Reads as vaporware to judges. Keep at most a "trend" badge computed from a rolling window — no simulation engine, no cohort modeling. |
| **Digital twin / scenario simulation** ("what if Gateway A fails") | **CUT** | Scope trap. Zero demo payoff for the effort. |
| **Live data ingestion / streaming** | **CUT to a replay toggle** | Seeded batch + a "replay as stream" button that animates the same batch. No Kafka, no webhooks. |
| **Voice AI / Hinglish calls** | **CUT** | Impressive-looking, but it's the crowded part of the market and eats a full day. Mock the channel; log the "call". |
| Neo4j / Qdrant / Redis / Inngest | **CUT** | Not needed for one batch. SQLite + in-process orchestration. Add nothing you have to deploy. |

---

## 3. How it differs

**From the market (PraecisAI / CreditNirvana / FinanceOps / dunning tools):**
they start *after* "payment failed" and optimize *who to remind*. Revenue Sherlock leads
with *why* revenue is leaking (issuer / method / region / gateway attribution) and routes
the intervention to the **cause**, not the customer — card-expiry → update-card link,
salary-cycle → retry on payday, gateway degradation → reroute, overdue invoice → finance
escalation. Recovery is the last step, not the product.

**From other hackathon teams (who will all build AI caller + WhatsApp bot + dashboard):**
we show a **causal leak graph**, a **compliance panel** that visibly enforces stopping
rules, and a **batch result with a hard ₹-recovered number and a per-event audit receipt**.
That is a product a payments company would deploy, not a demo.

**The one-sentence judge takeaway:** *"Where is revenue leaking, why, how much will we
lose, and what did the agent do about it — with receipts."*

---

## 3.5 How judges score this — and where we win

A judge does not care about the stack. They score whether the product solves the problem
better than the others. Assumed rubric:

| Parameter | Weight | Judge's question | Our answer on the day |
|---|---|---|---|
| **Problem fit** | 25% | Does this actually recover revenue? | Hero metric: 400 events, ₹12.4L at risk, ₹4.9L recovered, 39%. A number, on screen. |
| **Differentiation** | 20% | Why isn't this just a reminder bot? | We route by **root cause** (card-expiry → card link, salary-cycle → retry on payday, gateway degradation → reroute). Recovery is the last step. |
| **Measurable impact** | 20% | How much money? | ₹ recovered **vs a naive baseline** (24%) so 39% has meaning. Plus net-of-cost ROI (§17). |
| **Technical depth** | 15% | Real intelligence or just rules? | Attribution is deterministic cross-batch analytics; the LLM **explains** findings and answers questions over the audit log. It never invents evidence (§16). |
| **Feasibility** | 10% | Could a company deploy this? | Decision engine, compliance engine, audit system, recovery workflow are **real**; only the outside world is mocked. Clean boundary. |
| **Demo quality** | 10% | Can I get it in 2 minutes? | One hero slide + one event walkthrough + compliance panel + baseline flip. Script in §13. |

### The one slide that decides it

```
Revenue Sherlock
  Events processed:   400
  Revenue at risk:    ₹12.4L
  Recovered revenue:  ₹4.9L
  Recovery rate:      39%      (naive baseline: 24%)
  Top cause:          ICICI UPI timeout — South India, Android
  Compliance:         22 deferred · 8 suppressed · 14 stopped
  Audit coverage:     100%
```

If a judge sees that and believes the demo, we have answered: what problem, what the AI
found, what action was taken, how much was recovered, and whether it was done safely.

---

## 4. Scope — 3 days

### In
- Seed dataset generator: ~400 at-risk events across 4 types (failed payment, abandoned
  checkout, overdue invoice, failed subscription renewal), with hidden true-cause + a
  responsiveness parameter per event/customer.
- 5-stage pipeline (agents as typed functions; LLM used for diagnosis narrative, plan
  rationale, and chat — see §6).
- Deterministic, seeded outcome engine (§7) so the demo is identical every run.
- Compliance / stopping-rules engine (§8) — enforced, and surfaced in the UI.
- Append-only audit log; ₹-recovered math.
- **Auto Mode / Review Mode** toggle — in Review Mode, outreach + escalation actions
  queue for human approval instead of executing (§16).
- PII masking at the model boundary + tokenized payment references only (§15).
- Web dashboard (§9): Command Center, Batch Run table, Leak Graph, Audit Trail,
  Compliance panel, Review queue, Chat.
- "Run batch" + "Replay as stream" controls.

### Out (explicitly)
Real gateway calls · real WhatsApp/email/SMS sends · voice · prediction/simulation ·
live ingestion · auth/multi-tenant · mobile app · anything needing a deployed datastore.

---

## 5. Architecture

```
Seed data (SQLite) ──▶ Batch Runner
                          │  for each event:
                          ▼
   ┌── 1. Triage ──────────── classify type, expected_loss, recoverability, priority
   ├── 2. Root Cause ──────── correlate across batch (issuer/method/region/gateway/time)
   │                          → cause + confidence + graph edges   [LLM writes the narrative]
   ├── 3. Plan ───────────── policy table: cause + customer state → action,
   │                          gated by Compliance engine (§8)      [LLM writes rationale]
   ├── 4. Execute ─────────── mock connector; outcome from seeded engine (§7)
   └── 5. Audit ───────────── append log entry; if success, add to recovered ₹
                          │
                          ▼
              Aggregates + Leak Graph + Audit Trail  ──▶  Dashboard / Chat
```

Orchestration: a plain typed async pipeline (Pydantic models, one function per stage).
**No LangGraph** unless we have spare time on Day 3 and want a "framework" bullet — the
React Flow graph already gives the visual, and a hand-rolled pipeline is faster and does
not break.

---

## 6. Data model (SQLite via SQLModel)

- **customer**: id, name, segment (B2C/B2B), region, method_pref, dnd, opt_out,
  contact_count_7d, last_contacted_at, promise_to_pay_date (nullable), on_hold (bool),
  `responsiveness` (0–1, hidden).
- **revenue_event**: id, type (`payment_failed|checkout_abandoned|invoice_overdue|subscription_failed`),
  customer_id, amount, currency, created_at, gateway, method, issuer/bin, status,
  `true_cause` (hidden enum), meta (json).
- **diagnosis**: event_id, cause, confidence, evidence (json: the cross-batch stats used),
  narrative (LLM).
- **plan**: event_id, action (`smart_retry|retry_on_payday|reroute_gateway|update_card_link|
  dunning_email|payment_link_nudge|finance_escalation|no_action_stop`), rationale (LLM),
  blocked_by (nullable compliance rule id).
- **execution**: event_id, action, channel, attempted_at, outcome (`recovered|partial|failed|deferred|suppressed|awaiting_review`),
  amount_recovered, outreach_cost.
- **review_item**: event_id, action, rationale, status (`pending|approved|rejected`),
  decided_by, decided_at. Only created in Review Mode for outreach/escalation actions.
- **audit_entry**: id, ts, event_id, stage, actor (`agent|compliance|system|human`), detail (json).
  Append-only; never updated. Diagnosis entries store the exact `evidence` stats the cause
  was derived from.

Cause enum (shared by `true_cause`, `diagnosis.cause`, policy table):
`card_expired · insufficient_funds_salary_cycle · issuer_downtime · gateway_degradation ·
upi_timeout · checkout_latency · price_shock_shipping · mandate_revoked · forgot_to_pay ·
disputed`.

---

## 7. Deterministic outcome engine

The demo must be identical every run. Executor does **not** call anything real.

- Each event has a hidden `true_cause`; each customer a hidden `responsiveness`.
- `recovery_probability = base[action][true_cause] * (0.5 + 0.5*responsiveness)`, clamped.
  `base` is a small hand-tuned matrix — right action for the cause ≈ 0.6–0.85, wrong
  action ≈ 0.05–0.2.
- Draw outcome from a **seeded** RNG (`seed = hash(event_id)`), so results are stable but
  look stochastic. `partial` for invoices (promise-to-pay), `deferred` for quiet-hours,
  `suppressed` for opt-out/cap hits.
- `amount_recovered` = full amount on `recovered`, a seeded fraction on `partial`, else 0.

Tuning target: batch-level recovery rate lands ~35–45% of ₹-at-risk with the agent's
chosen actions, and visibly *lower* if you force a naive "retry everything" baseline
(build that toggle — it's a strong demo contrast).

---

## 8. Compliance / stopping-rules engine (the rubric winner)

Every planned action passes through this before execution. Each block is logged with a
rule id and shown in the Compliance panel.

1. **Contact cap** — max 3 outreach attempts / customer / rolling 7 days.
2. **Channel cooldown** — ≤ 1 outreach channel per customer per 24h.
3. **Quiet hours** — 21:00–09:00 IST → `deferred`, not sent.
4. **DND / opt-out** — honor list; outreach → `suppressed` (silent retries still allowed).
5. **Promise-to-pay hold** — if `promise_to_pay_date` in future → stop outreach until due.
6. **Manual hold / dispute** — `on_hold` or cause `disputed` → route to human, no automated action.
7. **Discount guardrail** — coupon action ≤ configured %, once per customer, only for
   `checkout_abandoned` / `price_shock_shipping`.
8. **Economic stop** — if `expected_recovery_value < cost_of_contact` → `no_action_stop`.
9. **Global batch cap** — hard ceiling on total outreach actions per run (config).
10. **Review Mode gate** — when Auto Mode is off, every outreach/escalation action is held
    as a `review_item` (`awaiting_review`) until a human approves; silent fixes still run.

Escalation ladder (per event, capped): silent fix (retry/reroute/card-link) →
1 low-friction nudge → 1 richer nudge (link + incentive if allowed) → finance/human
escalation → stop.

Every block and every hold is an audit entry with the rule id, so "why didn't it contact
this customer?" always has an answer on screen.

---

## 9. Dashboard (Next.js + Tailwind + shadcn/ui + Recharts + React Flow)

- **Command Center** — ₹ at risk · ₹ recovered · recovery rate · # events · recovered-by-cause
  bar · agent-vs-naive-baseline toggle · **net recovery** (recovered − outreach cost) ·
  Auto/Review Mode switch · audit coverage %.
- **Batch Run** — table: event, customer, type, ₹, diagnosed cause + confidence, action,
  compliance status, outcome, ₹ recovered. Row → detail drawer with the full stage trace.
- **Leak Graph** — React Flow. Nodes: gateway/issuer/method/region → failure mode →
  event cluster → ₹ loss. Edge weight = ₹. This is the hero screen.
- **Audit Trail** — filterable append-only log (by event, stage, actor, outcome).
- **Compliance** — counters: deferred (quiet hours), suppressed (opt-out/cap), stopped
  (economic/hold), escalated to human. Shows the system refusing to spam.
- **Review queue** — pending `review_item`s with the diagnosis + rationale; Approve /
  Reject buttons; decision lands in the audit log as `actor: human`. Empty in Auto Mode.
- **Chat** — "why is revenue down?" / "what did you do for customer X?" → answer grounded
  in batch aggregates + audit log (stuff context into the prompt; no vector DB for one batch).

Controls: **Run batch**, **Replay as stream** (animates the same batch), **seed** selector,
**naive baseline** toggle.

---

## 9.5 UX & motion direction

Reference: soft-pastel "clay" 3D UI — floating squircle cards with depth, organic accent
shapes, a persistent floating action bar, everything animating in space rather than just
appearing. We keep that feel for surfaces and chrome, but a finance product lives or dies
on *legible numbers*, so data and status get high contrast and semantic color.

### Palette (tokens — tune in Tailwind config)

| Token | Hex (approx) | Use |
|---|---|---|
| `bg` | `#F1EADB` | app background (warm cream) |
| `surface` | `#FBF7F0` | cards |
| `surface-sunk` | `#ECE4D3` | wells, table header, insets |
| `sage` | `#8FB89E` / deep `#5E9E7E` | primary brand, positive |
| `blue` | `#9DBFC9` / deep `#6E9AA8` | secondary, "deferred / hold" |
| `peach` | `#EEC0A0` / deep `#E8A87C` | accent, "escalated to human" |
| `ink` | `#3B3A36` | primary text |
| `ink-soft` | `#6B6860` | secondary text |
| shadow | `0 10px 30px -12px rgba(60,55,45,.28)` | the soft floating-card shadow |

### Semantic colors (outcomes — do NOT render these in pastel)

`recovered` → deep sage `#4F9575` · `failed` → clay terracotta `#C0705A` (not alarm-red) ·
`partial` → amber `#D9A441` · `deferred` → deep blue `#6E9AA8` · `suppressed` → warm grey
`#A79E8E` · `awaiting_review` / `escalated` → deep peach `#D68E63`.

### Shape & layout

- Squircle cards, radius 20–28px, generous padding (20–28px), lots of negative space.
- Left rail: icon nav (Command Center, Batch Run, Leak Graph, Audit, Compliance, Review, Chat).
- **Floating action bar**, bottom-center, glass/blur surface: seed selector · baseline
  toggle · Auto/Review switch · large circular **primary** button = *Run batch* (becomes
  *Replay* after a run).
- One or two organic blob accents per screen, low opacity, behind cards — never over text.
- Numbers are the loudest thing on every screen: large, `ink`, tabular-nums.

### Motion (library: Framer Motion; React Flow for the graph)

- **Easing:** spring (`stiffness 180, damping 22`) for anything that moves position;
  `ease-out` 240ms for fades.
- **Card enter:** `opacity 0, y 16, scale .96` → settle. Duration ~360ms. **Stagger 50ms**
  down a list / across a grid.
- **Depth parallax:** hero cards shift 2–4px against pointer movement. Subtle. Off on touch.
- **Run batch:** event cards travel left→right through the 5 pipeline stages (Triage →
  Root Cause → Plan → Execute → Audit) as columns; each card lands in its outcome color.
  In "Replay as stream", one card enters every ~120ms.
- **Count-up:** all ₹ / rate / count tiles animate from 0 (or previous value) over ~800ms
  `ease-out` when a run completes.
- **Leak Graph:** edges use an animated dashed flow, stroke width ∝ ₹; nodes settle with
  the same spring on layout.
- **Drawer:** slides from right with spring; the stage trace inside reveals stage-by-stage
  with the 50ms stagger.
- **Respect `prefers-reduced-motion`:** replace all travel/parallax with plain cross-fades;
  keep count-ups instant.

Keep motion in service of the story — cards flowing through stages *is* the "detect →
diagnose → plan → execute → audit" pitch, made visible.

---

## 10. Fake vs real

| Real | Mocked |
|---|---|
| Agent pipeline + stage orchestration | Payment gateway calls |
| Root-cause attribution logic (real cross-batch stats) | WhatsApp / email / SMS / voice sends (logged, simulated) |
| Compliance / stopping-rules engine | "Prediction" (static trend badge only) |
| Audit trail + ₹-recovered math | Live data ingestion (seeded batch + replay) |
| LLM calls: diagnosis narrative, plan rationale, chat | Multi-tenant / auth |
| Full dashboard incl. Leak Graph | — |
| Deterministic outcome engine (real seeded model) | — |
| PII masking at model boundary + tokenized payment refs (§15) | — |
| Auto/Review Mode + human approval queue (§16) | — |

Rule: the **decisions and receipts are real**; only the **outside world is stubbed**. Say
this out loud in the demo — judges respect a clean boundary.

---

## 11. Stack + LLM

- **Frontend:** Next.js (App Router) · Tailwind (custom pastel tokens, §9.5) · shadcn/ui ·
  Framer Motion · Recharts · React Flow.
- **Backend:** FastAPI (Python). Faster to write the pipeline + LLM glue than Node here.
- **DB:** SQLite via SQLModel. Postgres only if there is spare time; there won't be.
- **Orchestration:** plain typed async pipeline. LangGraph optional, Day-3-only, only for
  a talking point.
- **No** Redis / Qdrant / Neo4j / Inngest / Kafka.

### LLM choice

Put every model call behind one function — `llm(system, prompt, schema=None) -> str|obj`
— so the provider is swappable and the architecture never depends on it.

- **Primary: Claude Sonnet** (`claude-sonnet-5`) for the three reasoning jobs (diagnosis
  narrative, plan rationale, chat). Strong structured-output + instruction-following,
  1M context (whole batch fits), $2 / $10 per 1M tok. Use adaptive thinking
  (`thinking: {type: "adaptive"}`); default `effort` low–medium for narratives, medium
  for chat.
- **Cheap path (optional):** Claude Haiku 4.5 (`claude-haiku-4-5`) for the short
  per-event narrative strings if token spend matters during dev.
- Don't build a multi-model cascade. One model, one cache namespace, done.
- If the team has OpenAI/Gemini credits instead, that's fine — same single-function
  abstraction, swap the implementation. Do not let it leak into the pipeline.
- Keep prompts strict: JSON schema out for diagnosis/plan (`output_config.format` or
  `strict: true` tools), parse with `json.loads`.

---

## 12. Day-by-day

- **Day 1** — data model + seed generator + outcome engine + pipeline stages 1–5 +
  compliance engine + audit log. Backend `POST /run`, `GET /results`, `GET /graph`,
  `GET /audit`. No LLM yet (stub narratives), get numbers flowing.
- **Day 2** — wire Claude into stages 2–3. Build dashboard: Command Center, Batch Run
  table + drawer, Audit Trail. Naive-baseline toggle.
- **Day 3** — Leak Graph (React Flow), Compliance panel, Review queue, Chat endpoint + UI,
  "replay as stream", ROI/net-recovery tile, PII-masking pass, polish, tune the outcome
  matrix, rehearse demo, **record a fallback video**.

---

## 13. Demo script (2 minutes)

1. Command Center: "₹12.4L at risk across 400 events this batch."
2. Click **Run batch**. Numbers move: "₹4.9L recovered, 39%. Net of ₹7K outreach cost:
   ₹4.83L."
3. Leak Graph: "68% of the loss traces to two things — ICICI issuer downtime and UPI
   timeouts on Android in the south. Not random."
4. Batch Run drawer on one event: triage → diagnosis (cause + **the evidence stats it came
   from**) → plan (reroute, with rationale) → execution (recovered ₹) → audit receipt.
   "The LLM wrote the explanation; the cause came from cross-batch analytics, not a guess."
5. Compliance panel: "It deferred 22 messages for quiet hours, suppressed 8 opt-outs,
   stopped 14 where contact cost more than the recoverable amount. It won't spam."
6. Flip to **Review Mode**, re-run: outreach actions land in the Review queue. Approve one
   → it executes, decision logged as `human`. "Auto or human-in-the-loop, same audit trail."
7. Flip **naive baseline**: "Retry-everything gets 24%. Diagnosis-routed gets 39%."
8. Chat: "Why is revenue down this week?" → grounded answer with the ₹ breakdown.
9. Close on the Enterprise Readiness slide (§19).

---

## 14. Risks / cut-first list

- Leak Graph eating time → ship a static pre-computed layout, skip live physics.
- Chat flaky → hard-scope to 3 intents (why down / what for customer X / show top causes);
  fall back to a templated answer from aggregates.
- LLM latency in demo → pre-run the batch, cache diagnoses; "Run batch" replays cached
  results with animation.
- Outcome matrix untuned → keep the `base[action][cause]` table tiny and legible; tune last.
- Review Mode running long → it's one boolean + one queue view; build it thin, it's worth
  a full rubric line on feasibility.

---

## 15. Security & data handling

The judge's real question: *can this leak customer or payment data?* Answers we can defend:

- **Model sees only diagnosis-relevant fields** — event type, amount, gateway, method,
  issuer/BIN, region, coarse timing, customer segment. A single `to_model_view(event)`
  function is the only path from DB to prompt.
- **PII masked at that boundary** — names → `Customer #1042`, email/phone → hashed handles,
  addresses → region only. The dashboard can show real names (local, trusted); the model
  and the audit `detail` blobs never get them.
- **No sensitive payment data, ever** — no PAN, no CVV, no bank credentials, no full card
  numbers. Only tokenized references + issuer metadata. Say this in exactly these words.
- **Least-context prompts** — per-event diagnosis gets that event + the aggregate stats it
  needs, not the whole customer history.
- **Audit log is append-only** — no update/delete path in code; every mutation is a new row.
- **Secrets** — LLM key in env only, never in the repo, never sent to the browser; all
  model calls go through the backend.

For the "at Razorpay scale" version (say this, don't build it): field-level encryption at
rest, per-tenant isolation, KMS-managed keys, SSO + RBAC on the dashboard, PII tokenization
service, data-retention windows on the audit store.

---

## 16. Reliability & explainability

- **The LLM cannot invent a root cause.** `diagnosis.cause` is chosen by deterministic
  cross-batch analytics (issuer failure rate vs baseline, method/region/gateway skew,
  time clustering). The LLM receives the computed stats and writes the *narrative* and the
  *plan rationale* — it never picks the cause or the action. This is the single most
  important architectural line in the pitch.
- **Every decision is a chain:** event → diagnosis (+ evidence stats) → plan (+ rationale
  + any compliance block) → execution (+ outcome) → audit receipt. Visible in the row
  drawer. If a judge distrusts a decision, they can trace it in 10 seconds.
- **Confidence gating** — diagnosis below a confidence threshold → cause = `undetermined`
  → conservative action only (silent retry or human review), never a discount or a spammy
  nudge on a weak guess.
- **Auto Mode / Review Mode** — Review Mode holds every outreach/escalation for human
  approval (§8 rule 10). Makes it deployable in a regulated setting without a rewrite.
- **Deterministic + seeded** — same input, same output. A wrong call is reproducible and
  therefore fixable, not a one-off.

---

## 17. Economics (ROI guardrail)

Ties directly to compliance rule 8 (economic stop). Surface on the Command Center:

```
Recovered revenue:  ₹4.9L
Outreach cost:       ₹7,000     (per-channel unit cost × sends)
Net recovery:        ₹4.83L
Cost per ₹ recovered: ₹0.014
Actions skipped on economics: 14   (recoverable value < contact cost)
```

Per-channel unit costs are config (`whatsapp`, `email`, `sms`, `voice`, `finance_touch`).
The point: the agent already knows when chasing a rupee costs more than a rupee, and stops.

---

## 18. Scale story (talk track, not a build item)

- Events are independent → the pipeline is embarrassingly parallel; stages 1–5 run per
  event, aggregates are a reduce.
- SQLite → Postgres/warehouse; in-process runner → a queue (one job per event); attribution
  aggregates → a nightly rollup or streaming window.
- Compliance state (contact counts, cooldowns) → a shared store keyed by customer.
- Nothing in the design assumes a single machine or a fixed batch size. Say "millions of
  events/day is a deployment change, not a redesign."

---

## 19. Enterprise Readiness slide (closing)

```
Revenue Sherlock — beyond "AI + dashboard"

  ✓ Root-cause attribution        deterministic, evidence-backed
  ✓ Measured recovery             ₹ recovered vs naive baseline
  ✓ Compliance engine             10 stopping rules, all enforced
  ✓ Audit trail                   append-only, 100% coverage
  ✓ Human override                Auto / Review Mode
  ✓ Opt-out enforcement           DND + cap + cooldown honored
  ✓ Economic guardrails           stops when contact > recoverable
  ✓ Explainable decisions         full chain per event
  ✓ Data safety                   PII masked, no card data, tokens only

  AI + Governance + Compliance + Auditability
```

Most teams stop at "AI + dashboard." For fintech judges, the governance half can matter as
much as the AI — recovery systems touch real customers and real money.
