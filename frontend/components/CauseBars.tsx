"use client";

/**
 * Recovered vs at-risk, per diagnosed cause. One series (recovered), so no legend — a
 * single-hue fill on a neutral at-risk track, direct-labelled. (dataviz: magnitude
 * across identity → bar; part-of-whole per row → bullet-style track+fill.)
 */

import { humanize, inrLakh, pct } from "@/lib/format";
import type { RecoveredByCause } from "@/lib/types";
import { Stagger, StaggerItem } from "./motion";

export function CauseBars({ rows }: { rows: RecoveredByCause[] }) {
  const max = Math.max(1, ...rows.map((r) => r.at_risk));
  return (
    <Stagger className="space-y-2.5" gap={0.04}>
      {rows.map((r) => {
        const rate = r.at_risk ? r.recovered / r.at_risk : 0;
        return (
          <StaggerItem key={r.cause}>
            <div className="flex items-center gap-3 text-sm">
              <span className="w-44 shrink-0 truncate text-ink-soft">{humanize(r.cause)}</span>
              <div className="relative h-3 flex-1 overflow-hidden rounded-full bg-surface-sunk">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-ink/12"
                  style={{ width: `${(r.at_risk / max) * 100}%` }}
                />
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-sage-deep"
                  style={{ width: `${(r.recovered / max) * 100}%` }}
                />
              </div>
              <span className="tnum w-36 shrink-0 text-right text-ink-soft">
                {inrLakh(r.recovered)} <span className="text-ink/40">/ {inrLakh(r.at_risk)}</span>
              </span>
              <span className="tnum w-11 shrink-0 text-right font-medium text-ink">{pct(rate, 0)}</span>
            </div>
          </StaggerItem>
        );
      })}
    </Stagger>
  );
}
