"use client";

import { motion } from "framer-motion";
import { useRun } from "@/lib/run-context";
import { SPRING } from "./motion";

function Pill({
  active,
  activeClass,
  onClick,
  children,
}: {
  active: boolean;
  activeClass: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        active ? activeClass : "bg-surface-sunk text-ink-soft hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function ActionBar() {
  const { seed, setSeed, mode, setMode, baseline, setBaseline, running, runNow, lastRun, error } = useRun();

  return (
    <motion.div
      initial={{ y: 48, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={SPRING}
      className="fixed bottom-5 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3 rounded-full border border-surface-sunk bg-surface/85 px-4 py-2.5 shadow-float backdrop-blur"
    >
      <label className="flex items-center gap-1.5 text-xs text-ink-soft">
        seed
        <input
          type="number"
          value={seed}
          onChange={(e) => setSeed(Number(e.target.value) || 0)}
          className="tnum w-14 rounded-md bg-surface-sunk px-2 py-1 text-ink outline-none focus:ring-1 focus:ring-sage"
        />
      </label>

      <Pill active={baseline} activeClass="bg-outcome-failed/20 text-outcome-failed" onClick={() => setBaseline(!baseline)}>
        {baseline ? "naive baseline" : "agent routing"}
      </Pill>

      <Pill
        active={mode === "review"}
        activeClass="bg-blue/30 text-blue-deep"
        onClick={() => setMode(mode === "auto" ? "review" : "auto")}
      >
        {mode === "auto" ? "Auto mode" : "Review mode"}
      </Pill>

      <button
        onClick={runNow}
        disabled={running}
        title={error ?? (lastRun ? "Re-run batch" : "Run batch")}
        className="flex h-11 w-11 items-center justify-center rounded-full bg-sage-deep text-lg text-surface shadow-float-sm transition-transform hover:scale-105 disabled:opacity-60"
      >
        {running ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-surface border-t-transparent" /> : lastRun ? "↻" : "▶"}
      </button>
    </motion.div>
  );
}
