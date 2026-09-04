"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { humanize } from "@/lib/format";
import type { AuditResponse } from "@/lib/types";
import { PageHeader } from "@/components/ui";

const STAGES = ["triage", "root_cause", "plan", "compliance", "execute", "audit"];
const ACTORS = ["agent", "compliance", "system", "human"];
const OUTCOMES = ["recovered", "partial", "failed", "deferred", "suppressed", "awaiting_review"];
const LIMIT = 150;

export default function AuditPage() {
  const { version } = useRun();
  const [data, setData] = useState<AuditResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [event, setEvent] = useState("");
  const [stage, setStage] = useState("");
  const [actor, setActor] = useState("");
  const [outcome, setOutcome] = useState("");

  useEffect(() => {
    let alive = true;
    const q = {
      event: event.trim() || undefined,
      stage: stage || undefined,
      actor: actor || undefined,
      outcome: outcome || undefined,
      limit: LIMIT,
    };
    api
      .audit(q)
      .then((d) => alive && (setData(d), setErr(null)))
      .catch((e: unknown) =>
        alive && setErr(e instanceof ApiClientError ? `${e.code}: ${e.message}` : "Cannot reach the API on :8000."),
      );
    return () => {
      alive = false;
    };
  }, [version, event, stage, actor, outcome]);

  const sel = "rounded-md border border-surface-sunk bg-surface px-2 py-1 text-sm text-ink outline-none";
  const dropdown = (val: string, set: (v: string) => void, label: string, opts: string[]) => (
    <select className={sel} value={val} onChange={(e) => set(e.target.value)}>
      <option value="">{label}</option>
      {opts.map((o) => (
        <option key={o} value={o}>
          {humanize(o)}
        </option>
      ))}
    </select>
  );

  return (
    <div>
      <PageHeader
        title="Audit Trail"
        subtitle={data ? `${data.entries.length} shown of ${data.total} entries` : "Loading…"}
      />
      {err && <p className="text-sm text-outcome-failed">{err}</p>}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          className={sel}
          placeholder="event id (evt_00042)"
          value={event}
          onChange={(e) => setEvent(e.target.value)}
        />
        {dropdown(stage, setStage, "any stage", STAGES)}
        {dropdown(actor, setActor, "any actor", ACTORS)}
        {dropdown(outcome, setOutcome, "any outcome", OUTCOMES)}
        {(event || stage || actor || outcome) && (
          <button
            onClick={() => {
              setEvent("");
              setStage("");
              setActor("");
              setOutcome("");
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
              {["ID", "Time", "Event", "Stage", "Actor", "Detail"].map((h) => (
                <th key={h} className="px-3 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data?.entries ?? []).map((e) => (
              <tr key={e.id} className="border-t border-surface-sunk align-top">
                <td className="px-3 py-1.5 font-mono text-xs text-ink/40">{e.id}</td>
                <td className="tnum whitespace-nowrap px-3 py-1.5 text-xs text-ink-soft">{e.ts.slice(11, 19)}</td>
                <td className="px-3 py-1.5 font-mono text-xs">{e.event_id}</td>
                <td className="whitespace-nowrap px-3 py-1.5">{humanize(e.stage)}</td>
                <td className="px-3 py-1.5 text-ink-soft">{e.actor}</td>
                <td className="max-w-md truncate px-3 py-1.5 font-mono text-xs text-ink-soft">
                  {JSON.stringify(e.detail)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
