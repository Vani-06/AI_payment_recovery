"use client";

/**
 * Command Center — Phase 5 shell version: live headline metrics + run wiring.
 * The full dashboard (recovered-by-cause chart, count-ups) lands in Phase 6.
 */

import { useEffect, useState } from "react";
import { api, API_BASE, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { inrLakh, pct } from "@/lib/format";
import type { ResultsResponse } from "@/lib/types";
import { Card, Stat, Blob, PageHeader } from "@/components/ui";
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

  return (
    <div className="relative">
      <Blob className="left-40 top-10 h-64 w-64 bg-sage" />
      <Blob className="right-10 top-40 h-72 w-72 bg-blue" />

      <PageHeader
        title="Command Center"
        subtitle={
          data
            ? `seed ${data.run.seed} · ${data.run.mode}${data.run.baseline ? " · baseline" : ""} · ${data.run.event_count} events`
            : "Revenue recovery at a glance"
        }
      />

      {(err || runError) && (
        <Card className="border border-outcome-failed/40 text-sm text-outcome-failed">{err || runError}</Card>
      )}

      {a && (
        <Stagger className="grid grid-cols-2 gap-4 sm:grid-cols-4" gap={0.05}>
          {[
            { label: "Revenue at risk", value: inrLakh(a.revenue_at_risk) },
            {
              label: "Recovered",
              value: inrLakh(a.revenue_recovered),
              sub: `${pct(a.recovery_rate)} · net ${inrLakh(a.net_recovery)}`,
            },
            {
              label: "Recovery rate",
              value: pct(a.recovery_rate),
              sub: `baseline ${pct(a.baseline_recovery_rate)}`,
            },
            {
              label: "Audit coverage",
              value: pct(a.audit_coverage, 0),
              sub: `${a.compliance.escalated} escalated · ${a.compliance.deferred} deferred`,
            },
          ].map((s) => (
            <StaggerItem key={s.label}>
              <Card>
                <Stat label={s.label} value={s.value} sub={s.sub} />
              </Card>
            </StaggerItem>
          ))}
        </Stagger>
      )}

      {!a && !err && <p className="mt-6 text-sm text-ink-soft">Loading the latest batch…</p>}
    </div>
  );
}
