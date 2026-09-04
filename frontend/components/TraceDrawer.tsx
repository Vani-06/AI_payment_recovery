"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { humanize, inr, pct } from "@/lib/format";
import type { EventTrace } from "@/lib/types";
import { Chip } from "./Chip";
import { SPRING, Stagger, StaggerItem } from "./motion";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <StaggerItem>
      <div className="rounded-card bg-surface p-4 shadow-float-sm">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-soft">{title}</p>
        {children}
      </div>
    </StaggerItem>
  );
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-0.5 text-sm">
      <span className="text-ink-soft">{k}</span>
      <span className="tnum text-right text-ink">{v}</span>
    </div>
  );
}

function StageList({ t }: { t: EventTrace }) {
  return (
    <Stagger className="mt-4 space-y-3" gap={0.06}>
      <Section title="1 · Triage">
        <KV k="priority" v={t.triage.priority} />
        <KV k="recoverability" v={pct(t.triage.recoverability, 0)} />
        <KV k="expected loss" v={inr(t.triage.expected_loss)} />
      </Section>

      <Section title="2 · Root cause">
        <div className="mb-1 flex items-center gap-2">
          <Chip value={t.diagnosis.cause} />
          <span className="tnum text-xs text-ink-soft">confidence {pct(t.diagnosis.confidence, 0)}</span>
        </div>
        <div className="mt-2 space-y-0.5 border-t border-surface-sunk pt-2">
          {Object.entries(t.diagnosis.evidence).map(([k, v]) => (
            <KV key={k} k={humanize(k)} v={typeof v === "object" ? JSON.stringify(v) : String(v)} />
          ))}
        </div>
        {t.diagnosis.narrative && <p className="mt-2 text-sm leading-relaxed text-ink">{t.diagnosis.narrative}</p>}
      </Section>

      <Section title="3 · Plan">
        <KV k="action" v={humanize(t.plan.action)} />
        <KV k="channel" v={t.plan.channel} />
        {t.plan.blocked_by && <KV k="blocked by" v={<Chip value="blocked" />} />}
        {t.plan.rationale && <p className="mt-2 text-sm leading-relaxed text-ink">{t.plan.rationale}</p>}
      </Section>

      <Section title="4 · Execute">
        <div className="mb-1">
          <Chip value={t.execution.outcome} />
        </div>
        <KV k="recovered" v={t.execution.amount_recovered ? inr(t.execution.amount_recovered) : "—"} />
        <KV k="outreach cost" v={t.execution.outreach_cost ? inr(t.execution.outreach_cost) : "—"} />
      </Section>

      <Section title="5 · Audit receipt">
        <div className="space-y-1">
          {t.audit.map((a) => (
            <div key={a.id} className="flex justify-between gap-2 text-xs">
              <span className="font-mono text-ink-soft">{a.stage}</span>
              <span className="text-ink-soft">{a.actor}</span>
              <span className="tnum text-ink/40">{a.ts.slice(11, 19)}</span>
            </div>
          ))}
        </div>
      </Section>
    </Stagger>
  );
}

export function TraceDrawer({ eventId, onClose }: { eventId: string | null; onClose: () => void }) {
  const [trace, setTrace] = useState<EventTrace | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setTrace(null);
    setErr(null);
    if (!eventId) return;
    let alive = true;
    api
      .event(eventId)
      .then((t) => alive && setTrace(t))
      .catch((e: unknown) =>
        alive && setErr(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "failed to load trace"),
      );
    return () => {
      alive = false;
    };
  }, [eventId]);

  return (
    <AnimatePresence>
      {eventId && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-ink/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-surface-sunk bg-bg p-5"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={SPRING}
          >
            <div className="flex items-center justify-between">
              <h2 className="font-mono text-sm text-ink">{eventId}</h2>
              <button onClick={onClose} className="text-ink-soft hover:text-ink" aria-label="close">
                ✕
              </button>
            </div>
            {err && <p className="mt-4 text-sm text-outcome-failed">{err}</p>}
            {!trace && !err && <p className="mt-4 text-sm text-ink-soft">Loading trace…</p>}
            {trace && <StageList t={trace} />}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
