"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { humanize, inrLakh } from "@/lib/format";
import type { LeakGraph as LeakGraphData } from "@/lib/types";
import { PageHeader, Card } from "@/components/ui";
import { LeakGraph } from "@/components/LeakGraph";

export default function LeakGraphPage() {
  const { version } = useRun();
  const [graph, setGraph] = useState<LeakGraphData | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .graph()
      .then((g) => alive && (setGraph(g), setErr(null)))
      .catch((e: unknown) =>
        alive && setErr(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "Cannot reach the API on :8000."),
      );
    return () => {
      alive = false;
    };
  }, [version]);

  const lossEdges = (graph?.edges ?? [])
    .filter((e) => e.target === "loss:total")
    .sort((a, b) => b.rupees - a.rupees);
  const totalLoss = graph?.nodes.find((n) => n.id === "loss:total")?.value ?? 0;

  return (
    <div>
      <PageHeader
        title="Leak Graph"
        subtitle="attribute → failure mode → revenue loss, weighted by rupees at risk."
      />
      {err && <p className="text-sm text-outcome-failed">{err}</p>}

      {graph && (
        <>
          <LeakGraph graph={graph} />

          <Card className="mt-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-soft">
              Where the {inrLakh(totalLoss)} of loss traces
            </p>
            <div className="space-y-1.5">
              {lossEdges.map((e) => {
                const cause = e.source.split(":", 2)[1] ?? e.source;
                const share = totalLoss ? e.rupees / totalLoss : 0;
                return (
                  <div key={e.source} className="flex items-center gap-3 text-sm">
                    <span className="w-48 shrink-0 text-ink-soft">{humanize(cause)}</span>
                    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-sunk">
                      <div
                        className="h-full rounded-full bg-outcome-failed/70"
                        style={{ width: `${share * 100}%` }}
                      />
                    </div>
                    <span className="tnum w-24 shrink-0 text-right text-ink-soft">{inrLakh(e.rupees)}</span>
                    <span className="tnum w-10 shrink-0 text-right font-medium text-ink">{e.label}</span>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}

      {!graph && !err && <p className="mt-6 text-sm text-ink-soft">Loading the graph…</p>}
    </div>
  );
}
