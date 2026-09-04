# Demo Runbook — Revenue Sherlock

**Seed: 7. Mode: Auto.** Everything below is deterministic — the same numbers every run.

## Before you walk on

```powershell
.\scripts\dev.ps1        # starts Postgres + backend + frontend, opens http://localhost:3000
```

Wait for `backend 200` / `frontend 200`. Open **http://localhost:3000**. If a key is set,
run `.\scripts\warm.ps1` once so narratives are pre-generated (skip if no `ANTHROPIC_API_KEY`
— templated prose is instant).

Leave the action bar at **seed 7 · agent routing · Auto mode**.

## The numbers (seed 7, memorise these)

| | |
|---|---|
| Revenue at risk | **₹59.1L** (400 events) |
| Recovered | **₹22.9L — 38.8%** |
| Naive baseline (same compliance) | **20.5%** → **+18.3 pts** |
| Net recovery | ₹22.9L (₹4,968 outreach cost) |
| Audit coverage | 100% |
| Compliance | deferred 14 · suppressed 18 · stopped 16 · escalated 22 |
| Diagnosis accuracy vs hidden truth | 93% |
| Top loss cause | forgot-to-pay (55%), then disputed (19%), mandate-revoked (17%) |

## Script — ~2 minutes

1. **Command Center.** "₹59.1L of revenue is at risk across 400 events this batch —
   failed payments, abandoned checkouts, failed renewals, overdue B2B invoices."
2. Hit the **▶ run** button (bottom bar). The **Pipeline** panel animates: events flow
   Triage → Root cause → Plan → Compliance → Execute and land coloured by outcome. The KPI
   tiles count up. "₹22.9L recovered — 38.8%. Net of outreach cost, ₹22.9L."
3. Point at the **+18.3 pts** tile. "That's versus 20.5% for naive retry-everything —
   through the *same* compliance rules. The gain is routing by root cause."
4. **Leak Graph** (rail). "The loss isn't random. 55% traces to overdue receivables,
   19% to disputed charges we deliberately don't chase, 17% to revoked mandates." The
   thick animated edges are the big money.
5. **Batch Run** (rail). Click any invoice row → the **trace drawer** slides in.
   "Every event has a receipt: triage → diagnosed cause *with the evidence stats* →
   the action and why → execution → audit trail. The model wrote the explanation; the
   cause came from cross-batch analytics, not a guess."
6. **Compliance** (rail). "It deferred 14 for quiet hours / promise-to-pay, suppressed 18
   for opt-out and contact caps, stopped 16 where the expected recovery wasn't worth the
   contact, and escalated 22 disputed / on-hold accounts to a human. It will not spam."
7. Flip **agent routing → naive baseline** in the bar, hit run. "Retry-everything: 20.5%.
   Diagnosis-routed: 38.8%." Flip back.
8. Flip **Auto → Review mode**, hit run, open **Review** (rail). "Same agent, human in the
   loop — every outreach queues. Approve one —" click **Approve** "— it executes now and
   the decision lands in the audit trail as `human`. Silent fixes still auto-run."
9. **Chat** (rail). Click *"Why is revenue down this week?"* → read the grounded answer.
10. Close on the story: **where is revenue leaking, why, how much, what did the agent do —
    with receipts.**

## If something breaks on stage

- Backend down → the screens show a red "Cannot reach the API" line. Restart:
  `cd backend; .venv\Scripts\python -m uvicorn app.main:app --port 8000`
- Weird numbers → `POST http://localhost:8000/admin/reset {"seed":7}` (or just hit run).
- Leak Graph blank → scroll down; the "where the loss traces" bar list is the same story.
- Total failure → play the fallback screen recording (see below).

## Fallback recording — record this before the event

Screen-capture the full script above with voiceover, on a clean `.\scripts\dev.ps1` start.
Keep it under 3 minutes. Save as `demo-fallback.mp4` outside the repo. This is the only
Phase 9 item a human has to do.
