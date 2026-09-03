/**
 * Typed API client — Phase 0 skeleton. Endpoints get real handlers in Phase 3/4;
 * the shapes are frozen now (see docs/CONTRACT.md).
 */

import type {
  AuditResponse,
  ChatResponse,
  ComplianceReport,
  EventTrace,
  LeakGraph,
  ResultsResponse,
  ReviewDecisionResponse,
  ReviewQueue,
  ReviewStatus,
  RunRequest,
  RunSummary,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const code = body?.error?.code ?? "internal";
    const message = body?.error?.message ?? res.statusText;
    throw new ApiClientError(res.status, code, message);
  }
  return body as T;
}

export const api = {
  health: () => req<{ status: string; phase: string }>("/health"),

  results: (q: { limit?: number; offset?: number; outcome?: string; cause?: string } = {}) => {
    const s = new URLSearchParams(
      Object.entries(q).filter(([, v]) => v !== undefined) as [string, string][],
    ).toString();
    return req<ResultsResponse>(`/results${s ? `?${s}` : ""}`);
  },

  run: (payload: RunRequest) =>
    req<RunSummary>("/run", { method: "POST", body: JSON.stringify(payload) }),

  event: (id: string) => req<EventTrace>(`/event/${id}`),

  graph: () => req<LeakGraph>("/graph"),

  audit: (q: { event?: string; stage?: string; actor?: string; outcome?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams(
      Object.entries(q).filter(([, v]) => v !== undefined) as [string, string][],
    ).toString();
    return req<AuditResponse>(`/audit${s ? `?${s}` : ""}`);
  },

  compliance: () => req<ComplianceReport>("/compliance"),

  reviewQueue: () => req<ReviewQueue>("/review"),

  reviewDecide: (eventId: string, decision: Exclude<ReviewStatus, "pending">) =>
    req<ReviewDecisionResponse>(`/review/${eventId}`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),

  chat: (question: string) =>
    req<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ question }) }),
};

export { ApiClientError, BASE as API_BASE };
