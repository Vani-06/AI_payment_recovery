"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { humanize } from "@/lib/format";
import type { ComplianceReport } from "@/lib/types";
import { PageHeader, Card } from "@/components/ui";
import { Chip } from "@/components/Chip";
import { Num } from "@/components/Num";
import { Stagger, StaggerItem } from "@/components/motion";

const COUNTER_META: { key: keyof ComplianceReport["counters"]; label: string; cls: string }[] = [
  { key: "auto_executed", label: "auto-executed", cls: "text-sage-deep" },
  { key: "deferred", label: "deferred", cls: "text-outcome-deferred" },
  { key: "suppressed", label: "suppressed", cls: "text-outcome-suppressed" },
  { key: "stopped", label: "stopped (economics)", cls: "text-ink" },
  { key: "escalated", label: "escalated to human", cls: "text-outcome-review" },
  { key: "awaiting_review", label: "awaiting review", cls: "text-outcome-review" },
];

export default function CompliancePage() {
  const { version } = useRun();
  const [data, setData] = useState<ComplianceReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rule, setRule] = useState("");

  useEffect(() => {
    let alive = true;
    api
      .compliance()
      .then((d) => alive && (setData(d), setErr(null)))
      .catch((e: unknown) =>
        alive && setErr(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "Cannot reach the API on :8000."),
      );
    return () => {
      alive = false;
    };
  }, [version]);

  const rules = useMemo(
    () => Array.from(new Set((data?.items ?? []).map((i) => i.rule_id))).sort(),
    [data],
  );
  const items = (data?.items ?? []).filter((i) => !rule || i.rule_id === rule);
  const c = data?.counters;

  return (
    <div>
      <PageHeader
        title="Compliance"
        subtitle="Every action passes the stopping rules before execution. The system will not spam."
      />
      {err && <p className="text-sm text-outcome-failed">{err}</p>}

      {c && (
        <>
          <Stagger className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" gap={0.04}>
            {COUNTER_META.map((m) => (
              <StaggerItem key={m.key}>
                <Card className="p-4 text-center">
                  <p className={`tnum text-2xl font-semibold ${m.cls}`}>
                    <Num value={c[m.key]} format={(n) => `${Math.round(n)}`} />
                  </p>
                  <p className="mt-0.5 text-xs text-ink-soft">{m.label}</p>
                </Card>
              </StaggerItem>
            ))}
          </Stagger>

          <div className="mt-4 mb-3 flex flex-wrap items-center gap-2">
            <select
              className="rounded-md border border-surface-sunk bg-surface px-2 py-1 text-sm text-ink outline-none"
              value={rule}
              onChange={(e) => setRule(e.target.value)}
            >
              <option value="">all rules ({data?.items.length})</option>
              {rules.map((r) => (
                <option key={r} value={r}>
                  {humanize(r)}
                </option>
              ))}
            </select>
            {rule && (
              <button onClick={() => setRule("")} className="text-xs text-ink-soft underline hover:text-ink">
                clear
              </button>
            )}
          </div>

          <div className="overflow-x-auto rounded-card bg-surface shadow-float">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-sunk text-xs uppercase tracking-wide text-ink-soft">
                <tr>
                  {["Event", "Rule", "Disposition", "Detail"].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((i, n) => (
                  <tr key={`${i.event_id}-${n}`} className="border-t border-surface-sunk align-top">
                    <td className="px-3 py-1.5 font-mono text-xs">{i.event_id}</td>
                    <td className="whitespace-nowrap px-3 py-1.5">{i.rule_label}</td>
                    <td className="px-3 py-1.5">
                      <Chip value={i.disposition} />
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs text-ink-soft">{JSON.stringify(i.detail)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
