"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { humanize, inr, pct } from "@/lib/format";
import type { ResultsResponse } from "@/lib/types";
import { PageHeader } from "@/components/ui";
import { Chip } from "@/components/Chip";
import { TraceDrawer } from "@/components/TraceDrawer";

const OUTCOMES = ["recovered", "partial", "failed", "deferred", "suppressed", "awaiting_review"];
const HEAD = ["Event", "Customer", "Type", "₹ at risk", "Cause", "Action", "Compliance", "Outcome", "Recovered"];

export default function BatchRunPage() {
  const { version } = useRun();
  const [data, setData] = useState<ResultsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [fOutcome, setFOutcome] = useState("");
  const [fCause, setFCause] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .results({ limit: 400 })
      .then((d) => alive && (setData(d), setErr(null)))
      .catch((e: unknown) =>
        alive && setErr(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "Cannot reach the API on :8000."),
      );
    return () => {
      alive = false;
    };
  }, [version]);

  const causes = useMemo(
    () => Array.from(new Set((data?.rows ?? []).map((r) => r.cause))).sort(),
    [data],
  );
  const rows = useMemo(
    () =>
      (data?.rows ?? []).filter(
        (r) => (!fOutcome || r.outcome === fOutcome) && (!fCause || r.cause === fCause),
      ),
    [data, fOutcome, fCause],
  );

  const sel = "rounded-md border border-surface-sunk bg-surface px-2 py-1 text-sm text-ink outline-none";

  return (
    <div>
      <PageHeader
        title="Batch Run"
        subtitle={data ? `${rows.length} of ${data.rows.length} events` : "Loading…"}
      />
      {err && <p className="text-sm text-outcome-failed">{err}</p>}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select className={sel} value={fOutcome} onChange={(e) => setFOutcome(e.target.value)}>
          <option value="">all outcomes</option>
          {OUTCOMES.map((o) => (
            <option key={o} value={o}>
              {humanize(o)}
            </option>
          ))}
        </select>
        <select className={sel} value={fCause} onChange={(e) => setFCause(e.target.value)}>
          <option value="">all causes</option>
          {causes.map((c) => (
            <option key={c} value={c}>
              {humanize(c)}
            </option>
          ))}
        </select>
        {(fOutcome || fCause) && (
          <button
            onClick={() => {
              setFOutcome("");
              setFCause("");
            }}
            className="text-xs text-ink-soft underline hover:text-ink"
          >
            clear
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-card bg-surface shadow-float">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-sunk text-xs uppercase tracking-wide text-ink-soft">
            <tr>
              {HEAD.map((h) => (
                <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.event_id}
                onClick={() => setOpen(r.event_id)}
                className="cursor-pointer border-t border-surface-sunk transition-colors hover:bg-surface-sunk/50"
              >
                <td className="px-3 py-2 font-mono text-xs">{r.event_id}</td>
                <td className="whitespace-nowrap px-3 py-2 text-ink-soft">{r.customer_label}</td>
                <td className="whitespace-nowrap px-3 py-2">{humanize(r.type)}</td>
                <td className="tnum whitespace-nowrap px-3 py-2">{inr(r.amount)}</td>
                <td className="whitespace-nowrap px-3 py-2">
                  {humanize(r.cause)} <span className="tnum text-ink/40">{pct(r.confidence, 0)}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2">{humanize(r.action)}</td>
                <td className="px-3 py-2">
                  <Chip value={r.compliance_status} />
                </td>
                <td className="px-3 py-2">
                  <Chip value={r.outcome} />
                </td>
                <td className="tnum whitespace-nowrap px-3 py-2">
                  {r.amount_recovered ? inr(r.amount_recovered) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <TraceDrawer eventId={open} onClose={() => setOpen(null)} />
    </div>
  );
}
