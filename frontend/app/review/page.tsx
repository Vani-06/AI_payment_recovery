"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { humanize, inr, pct } from "@/lib/format";
import type { EventRow, ReviewItem } from "@/lib/types";
import { PageHeader, Card } from "@/components/ui";
import { Chip } from "@/components/Chip";
import { AnimatePresence, motion } from "framer-motion";
import { SPRING } from "@/components/motion";

type QueueCard = ReviewItem & Partial<Pick<EventRow, "cause" | "confidence" | "amount" | "customer_label" | "type">>;

export default function ReviewPage() {
  const { version, mode } = useRun();
  const [cards, setCards] = useState<QueueCard[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [q, res] = await Promise.all([api.reviewQueue(), api.results({ limit: 400 })]);
      const byId = new Map(res.rows.map((r) => [r.event_id, r]));
      setCards(
        q.items.map((it): QueueCard => {
          const r = byId.get(it.event_id);
          return { ...it, cause: r?.cause, confidence: r?.confidence, amount: r?.amount, customer_label: r?.customer_label, type: r?.type };
        }),
      );
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "Cannot reach the API on :8000.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, version]);

  async function decide(id: string, decision: "approved" | "rejected") {
    setBusy(id);
    try {
      const res = await api.reviewDecide(id, decision);
      setCards((cs) => (cs ?? []).filter((c) => c.event_id !== id));
      const rec = res.execution?.amount_recovered ?? 0;
      setToast(
        decision === "approved"
          ? `Approved ${id} — ${res.execution?.outcome ?? "executed"}${rec ? `, recovered ${inr(rec)}` : ""}`
          : `Rejected ${id} — suppressed`,
      );
    } catch (e) {
      setToast(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "decision failed");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <div>
      <PageHeader
        title="Review Queue"
        subtitle="Outreach and escalation actions held for human approval. Silent fixes still auto-execute."
      />
      {err && <p className="text-sm text-outcome-failed">{err}</p>}

      {cards && cards.length === 0 && (
        <Card className="text-center text-sm text-ink-soft">
          {mode === "review"
            ? "Nothing pending. Re-run the batch (▶) to populate the queue."
            : "Empty in Auto mode. Flip to Review mode in the action bar, then run the batch."}
        </Card>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <AnimatePresence>
          {(cards ?? []).map((c) => (
            <motion.div
              key={c.event_id}
              layout
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={SPRING}
            >
              <Card className="flex h-full flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-ink-soft">{c.event_id}</span>
                  {c.amount != null && <span className="tnum text-sm font-medium">{inr(c.amount)}</span>}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  {c.cause && <Chip value={c.cause} />}
                  {c.confidence != null && <span className="tnum text-xs text-ink-soft">{pct(c.confidence, 0)}</span>}
                  <span className="text-ink-soft">→</span>
                  <span className="font-medium">{humanize(c.action)}</span>
                </div>
                {c.customer_label && <p className="text-xs text-ink-soft">{c.customer_label}</p>}
                {c.rationale && <p className="text-sm leading-relaxed text-ink">{c.rationale}</p>}
                <div className="mt-auto flex gap-2 pt-1">
                  <button
                    disabled={busy === c.event_id}
                    onClick={() => decide(c.event_id, "approved")}
                    className="rounded-full bg-sage-deep px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    disabled={busy === c.event_id}
                    onClick={() => decide(c.event_id, "rejected")}
                    className="rounded-full bg-surface-sunk px-3 py-1 text-xs font-medium text-ink-soft disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              </Card>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ y: 60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 60, opacity: 0 }}
            transition={SPRING}
            className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2 rounded-full bg-ink px-4 py-2 text-xs text-surface shadow-float"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
