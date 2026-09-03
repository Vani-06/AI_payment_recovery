"use client";

/**
 * Phase 0 smoke screen. Proves: Tailwind tokens render, the API client works, and the
 * frozen `ResultsResponse` shape round-trips from the backend fixture. Replaced by the
 * real Command Center in Phase 6.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, API_BASE, ApiClientError } from "@/lib/api";
import type { ResultsResponse } from "@/lib/types";

const inr = (n: number) => `₹${(n / 100000).toFixed(1)}L`;
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

const OUTCOME_CLASS: Record<string, string> = {
  recovered: "bg-outcome-recovered",
  partial: "bg-outcome-partial",
  failed: "bg-outcome-failed",
  deferred: "bg-outcome-deferred",
  suppressed: "bg-outcome-suppressed",
  awaiting_review: "bg-outcome-review",
};

export default function Page() {
  const [data, setData] = useState<ResultsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .results()
      .then(setData)
      .catch((e: unknown) =>
        setErr(
          e instanceof ApiClientError
            ? `${e.status} ${e.code}: ${e.message}`
            : `Cannot reach API at ${API_BASE} — is the backend running?`,
        ),
      );
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <p className="text-xs uppercase tracking-widest text-ink-soft">Revenue Sherlock</p>
      <h1 className="mt-1 text-2xl font-semibold">Phase 0 — scaffold &amp; contract</h1>
      <p className="mt-2 text-sm text-ink-soft">
        Reading <code className="rounded bg-surface-sunk px-1">GET {API_BASE}/results</code> (serves{" "}
        <code>fixtures/sample_results.json</code> until Phase 3).
      </p>

      {err && (
        <div className="mt-8 rounded-card border border-outcome-failed/40 bg-surface p-4 text-sm text-outcome-failed shadow-float-sm">
          {err}
        </div>
      )}

      {data && (
        <>
          <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ["At risk", inr(data.aggregates.revenue_at_risk)],
              ["Recovered", inr(data.aggregates.revenue_recovered)],
              ["Recovery rate", pct(data.aggregates.recovery_rate)],
              ["Baseline", pct(data.aggregates.baseline_recovery_rate)],
            ].map(([label, value]) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 180, damping: 22 }}
                className="rounded-card bg-surface p-5 shadow-float"
              >
                <p className="text-xs text-ink-soft">{label}</p>
                <p className="tnum mt-1 text-2xl font-semibold">{value}</p>
              </motion.div>
            ))}
          </div>

          <h2 className="mt-10 text-sm font-semibold text-ink-soft">
            {data.rows.length} sample rows
          </h2>
          <div className="mt-3 overflow-hidden rounded-card bg-surface shadow-float">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-sunk text-xs uppercase tracking-wide text-ink-soft">
                <tr>
                  <th className="px-4 py-2">Event</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Cause</th>
                  <th className="px-4 py-2">Action</th>
                  <th className="px-4 py-2">Outcome</th>
                  <th className="px-4 py-2 text-right">Recovered</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.event_id} className="border-t border-surface-sunk">
                    <td className="px-4 py-2 font-mono text-xs">{r.event_id}</td>
                    <td className="px-4 py-2">{r.type}</td>
                    <td className="px-4 py-2">{r.cause}</td>
                    <td className="px-4 py-2">{r.action}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs text-white ${
                          OUTCOME_CLASS[r.outcome] ?? "bg-ink-soft"
                        }`}
                      >
                        {r.outcome}
                      </span>
                    </td>
                    <td className="tnum px-4 py-2 text-right">
                      {r.amount_recovered ? `₹${r.amount_recovered.toLocaleString("en-IN")}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
