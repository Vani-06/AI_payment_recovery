"use client";

/**
 * The headline animation (SPEC §9.5): a sample of events travels left→right through the
 * five pipeline stages and drops into an outcome-coloured tray. "stream" replays it one
 * card at a time. Uses Framer `layout` — a card re-parents to the next column and the
 * spring animates the move.
 */

import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { inrShort } from "@/lib/format";
import { SPRING, useReducedMotionSafe } from "./motion";

const STAGES = ["Triage", "Root cause", "Plan", "Compliance", "Execute"];
const STEP_MS = 240;
const OUT: Record<string, string> = {
  recovered: "bg-outcome-recovered",
  partial: "bg-outcome-partial",
  failed: "bg-outcome-failed",
  deferred: "bg-outcome-deferred",
  suppressed: "bg-outcome-suppressed",
  awaiting_review: "bg-outcome-review",
};

interface Chip {
  id: string;
  amount: number;
  outcome: string;
  enter: number;
}

export function PipelineFlow() {
  const { version } = useRun();
  const reduced = useReducedMotionSafe();
  const [chips, setChips] = useState<Chip[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const sampleRef = useRef<{ id: string; amount: number; outcome: string }[]>([]);
  const startRef = useRef(0);
  const rafRef = useRef(0);

  const play = useCallback(
    (asStream: boolean) => {
      cancelAnimationFrame(rafRef.current);
      const spawn = asStream ? 130 : 34;
      const seeded = sampleRef.current.map((r, i) => ({ ...r, enter: i * spawn }));
      setChips(seeded);
      if (reduced) {
        setElapsed(1e7);
        return;
      }
      startRef.current = performance.now();
      setElapsed(0);
      const total = seeded.length * spawn + 6 * STEP_MS + 400;
      const loop = (t: number) => {
        const e = t - startRef.current;
        setElapsed(e);
        if (e < total) rafRef.current = requestAnimationFrame(loop);
      };
      rafRef.current = requestAnimationFrame(loop);
    },
    [reduced],
  );

  useEffect(() => {
    let alive = true;
    api
      .results({ limit: 400 })
      .then((d) => {
        if (!alive) return;
        const rows = d.rows;
        const step = Math.max(1, Math.ceil(rows.length / 30));
        sampleRef.current = rows
          .filter((_, i) => i % step === 0)
          .slice(0, 30)
          .map((r) => ({ id: r.event_id, amount: r.amount, outcome: r.outcome }));
        play(false);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [version, play]);

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  const colOf = (c: Chip) => Math.min(5, Math.floor((elapsed - c.enter) / STEP_MS));

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Pipeline</p>
        <div className="flex gap-2 text-xs">
          <button
            onClick={() => play(false)}
            className="rounded-full bg-surface-sunk px-2 py-0.5 text-ink-soft transition-colors hover:text-ink"
          >
            ▶ replay
          </button>
          <button
            onClick={() => play(true)}
            className="rounded-full bg-surface-sunk px-2 py-0.5 text-ink-soft transition-colors hover:text-ink"
          >
            stream
          </button>
        </div>
      </div>

      <div className="flex gap-2">
        {STAGES.map((s, col) => (
          <div key={s} className="min-h-[110px] flex-1 rounded-md bg-surface-sunk/50 p-2">
            <p className="mb-1 text-[10px] uppercase tracking-wide text-ink-soft">{s}</p>
            <div className="space-y-1">
              {chips
                .filter((c) => colOf(c) === col)
                .map((c) => (
                  <motion.div
                    layout
                    key={c.id}
                    transition={SPRING}
                    className="tnum rounded bg-surface px-1.5 py-0.5 text-[10px] text-ink-soft shadow-float-sm"
                  >
                    {inrShort(c.amount)}
                  </motion.div>
                ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-2 flex min-h-[30px] flex-wrap gap-1 rounded-md bg-surface-sunk/50 p-2">
        {chips
          .filter((c) => colOf(c) >= 5)
          .map((c) => (
            <motion.div
              layout
              key={c.id}
              transition={SPRING}
              title={`${c.id} · ${c.outcome}`}
              className={`h-3 w-3 rounded-full ${OUT[c.outcome] ?? "bg-ink-soft"}`}
            />
          ))}
      </div>
    </div>
  );
}
