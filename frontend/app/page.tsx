"use client";

/** Command Center — headline metrics + recovered-by-cause. Phase 6. */

import { useEffect, useState } from "react";
import { api, API_BASE, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { humanize, inrLakh, pct } from "@/lib/format";
import type { ResultsResponse } from "@/lib/types";
import { Card, Blob, PageHeader } from "@/components/ui";
import { Num } from "@/components/Num";
import { CauseBars } from "@/components/CauseBars";
import { Stagger, StaggerItem } from "@/components/motion";

export default function CommandCenter() {
  const { version, error: runError } = useRun();
  const [data, setData] = useState<ResultsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .results({ limit: 1 })
      .then((d) => alive && (setData(d), setErr(null)))
      .catch((e: unknown) =>
        alive &&
        setErr(
          e instanceof ApiClientError
            ? `${e.status} ${e.code}: ${e.message}`
            : `Cannot reach the API at ${API_BASE}. Start the backend on :8000.`,
        ),
      );
    return () => {
      alive = false;
    };
  }, [version]);

  const a = data?.aggregates;
  const delta = a ? a.recovery_rate - a.baseline_recovery_rate : 0;

  return (
    <div className="relative">
      <Blob className="left-40 top-4 h-64 w-64 bg-sage" />
      <Blob className="right-4 top-44 h-72 w-72 bg-blue" />

      <PageHeader
        title="Command Center"
        subtitle={
          data
            ? `seed ${data.run.seed} · ${data.run.mode}${data.run.baseline ? " · baseline routing" : ""} · ${data.run.event_count} events`
            : "Revenue recovery at a glance"
        }
      />

      {(err || runError) && (
        <Card className="border border-outcome-failed/40 text-sm text-outcome-failed">{err || runError}</Card>
      )}

      {a && (
        <>
          <Stagger className="grid grid-cols-2 gap-4 md:grid-cols-3" gap={0.05}>
            {[
              { label: "Revenue at risk", n: a.revenue_at_risk, fmt: inrLakh },
              { label: "Recovered", n: a.revenue_recovered, fmt: inrLakh, sub: `${pct(a.recovery_rate)} recovered` },
              { label: "Net recovery", n: a.net_recovery, fmt: inrLakh, sub: `−${inrLakh(a.outreach_cost)} outreach` },
              { label: "Recovery rate", n: a.recovery_rate, fmt: (x: number) => pct(x), sub: `baseline ${pct(a.baseline_recovery_rate)}` },
              { label: "Events processed", n: data!.run.event_count, fmt: (x: number) => `${Math.round(x)}` },
              { label: "Audit coverage", n: a.audit_coverage, fmt: (x: number) => pct(x, 0), sub: "every event, every stage" },
            ].map((s) => (
              <StaggerItem key={s.label}>
                <Card>
                  <p className="text-xs text-ink-soft">{s.label}</p>
                  <p className="tnum mt-1 text-2xl font-semibold text-ink">
                    <Num value={s.n} format={s.fmt} />
                  </p>
                  {s.sub && <p className="tnum mt-0.5 text-xs text-ink-soft">{s.sub}</p>}
                </Card>
              </StaggerItem>
            ))}
          </Stagger>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_2fr]">
            <Card className="flex flex-col justify-center">
              <p className="text-xs text-ink-soft">Agent vs naive baseline</p>
              <p className="tnum mt-1 text-3xl font-semibold text-sage-deep">
                +<Num value={delta * 100} format={(x) => x.toFixed(1)} /> pts
              </p>
              <p className="mt-1 text-xs text-ink-soft">
                {pct(a.recovery_rate)} routing by root cause vs {pct(a.baseline_recovery_rate)} retry-everything —
                same compliance rules.
              </p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                {(["deferred", "suppressed", "stopped"] as const).map((k) => (
                  <div key={k} className="rounded-md bg-surface-sunk py-1.5">
                    <span className="tnum block text-base font-semibold text-ink">{a.compliance[k]}</span>
                    {k}
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-soft">
                Recovered by cause
              </p>
              <CauseBars rows={a.recovered_by_cause} />
            </Card>
          </div>
        </>
      )}

      {!a && !err && <p className="mt-6 text-sm text-ink-soft">Loading the latest batch…</p>}
    </div>
  );
}
