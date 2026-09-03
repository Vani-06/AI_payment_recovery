/**
 * TS mirror of backend/app/schemas.py + backend/app/enums.py (frozen contract, Phase 0).
 * Human copy: docs/CONTRACT.md + docs/DATA.md. Change all of them together.
 *
 * Money is a whole-INR integer everywhere. Timestamps are ISO-8601 UTC strings.
 */

// ---- Enums (as string unions) --------------------------------------------------------

export type EventType =
  | "payment_failed"
  | "checkout_abandoned"
  | "invoice_overdue"
  | "subscription_failed";

export type Cause =
  | "card_expired"
  | "insufficient_funds_salary_cycle"
  | "issuer_downtime"
  | "gateway_degradation"
  | "upi_timeout"
  | "checkout_latency"
  | "price_shock_shipping"
  | "mandate_revoked"
  | "forgot_to_pay"
  | "disputed"
  | "undetermined";

export type Action =
  | "smart_retry"
  | "retry_on_payday"
  | "reroute_gateway"
  | "update_card_link"
  | "payment_link_nudge"
  | "dunning_email"
  | "coupon_offer"
  | "finance_escalation"
  | "no_action_stop";

export type Channel = "whatsapp" | "email" | "sms" | "voice" | "finance_touch" | "none";

export type Outcome =
  | "recovered"
  | "partial"
  | "failed"
  | "deferred"
  | "suppressed"
  | "awaiting_review";

export type Stage = "triage" | "root_cause" | "plan" | "compliance" | "execute" | "audit";

export type Actor = "agent" | "compliance" | "system" | "human";

export type Mode = "auto" | "review";

export type Segment = "b2c" | "b2b";

export type ComplianceRuleId =
  | "contact_cap"
  | "channel_cooldown"
  | "quiet_hours"
  | "dnd_optout"
  | "promise_to_pay_hold"
  | "manual_hold_dispute"
  | "discount_guardrail"
  | "economic_stop"
  | "global_batch_cap"
  | "review_mode_gate";

export type ComplianceDisposition = "passed" | "blocked" | "deferred" | "awaiting_review";

export type ReviewStatus = "pending" | "approved" | "rejected";

export type LeakNodeKind = "gateway" | "issuer" | "method" | "region" | "failure" | "loss";

export type ChatIntent = "why_down" | "customer_detail" | "top_causes" | "unknown";

// ---- Entities ----------------------------------------------------------------------

export interface CustomerMasked {
  id: string;
  label: string;
  segment: Segment;
  region: string;
  method_pref: string;
  dnd: boolean;
  opt_out: boolean;
  contact_count_7d: number;
  last_contacted_at: string | null;
  promise_to_pay_date: string | null;
  on_hold: boolean;
}

export interface EventPublic {
  id: string;
  type: EventType;
  customer_id: string;
  amount: number;
  currency: string;
  created_at: string;
  gateway: string;
  method: string;
  issuer: string;
  bin: string | null;
  status: string;
  meta: Record<string, unknown>;
}

export interface Triage {
  event_id: string;
  expected_loss: number;
  recoverability: number;
  priority: string;
}

export interface Diagnosis {
  event_id: string;
  cause: Cause;
  confidence: number;
  evidence: Record<string, unknown>;
  narrative: string;
}

export interface Plan {
  event_id: string;
  action: Action;
  channel: Channel;
  rationale: string;
  blocked_by: ComplianceRuleId | null;
}

export interface Execution {
  event_id: string;
  action: Action;
  channel: Channel;
  attempted_at: string;
  outcome: Outcome;
  amount_recovered: number;
  outreach_cost: number;
}

export interface ReviewItem {
  event_id: string;
  action: Action;
  rationale: string;
  status: ReviewStatus;
  decided_by: string | null;
  decided_at: string | null;
}

export interface AuditEntry {
  id: string;
  ts: string;
  event_id: string;
  stage: Stage;
  actor: Actor;
  detail: Record<string, unknown>;
}

// ---- Aggregates & derived views --------------------------------------------------

export interface RecoveredByCause {
  cause: Cause;
  at_risk: number;
  recovered: number;
}

export interface ComplianceCounters {
  deferred: number;
  suppressed: number;
  stopped: number;
  escalated: number;
  auto_executed: number;
  awaiting_review: number;
}

export interface BatchAggregates {
  revenue_at_risk: number;
  revenue_recovered: number;
  recovery_rate: number;
  baseline_recovery_rate: number;
  outreach_cost: number;
  net_recovery: number;
  cost_per_rupee_recovered: number;
  audit_coverage: number;
  recovered_by_cause: RecoveredByCause[];
  compliance: ComplianceCounters;
}

export interface RunInfo {
  seed: number;
  mode: Mode;
  baseline: boolean;
  ran_at: string;
  event_count: number;
}

export interface EventRow {
  event_id: string;
  customer_id: string;
  customer_label: string;
  type: EventType;
  amount: number;
  cause: Cause;
  confidence: number;
  action: Action;
  compliance_status: ComplianceDisposition;
  blocked_by: ComplianceRuleId | null;
  outcome: Outcome;
  amount_recovered: number;
}

export interface EventTrace {
  event: EventPublic;
  customer: CustomerMasked;
  triage: Triage;
  diagnosis: Diagnosis;
  plan: Plan;
  execution: Execution;
  audit: AuditEntry[];
}

export interface LeakNode {
  id: string;
  label: string;
  kind: LeakNodeKind;
  value: number;
}

export interface LeakEdge {
  source: string;
  target: string;
  rupees: number;
  label: string;
}

export interface LeakGraph {
  nodes: LeakNode[];
  edges: LeakEdge[];
}

export interface ComplianceItem {
  event_id: string;
  rule_id: ComplianceRuleId;
  rule_label: string;
  disposition: ComplianceDisposition;
  detail: Record<string, unknown>;
}

export interface ComplianceReport {
  counters: ComplianceCounters;
  items: ComplianceItem[];
}

// ---- Request / response envelopes ----------------------------------------------

export interface RunRequest {
  seed: number;
  mode: Mode;
  baseline: boolean;
}

export interface RunSummary {
  run: RunInfo;
  aggregates: BatchAggregates;
}

export interface ResultsResponse {
  run: RunInfo;
  aggregates: BatchAggregates;
  rows: EventRow[];
}

export interface AuditResponse {
  entries: AuditEntry[];
  total: number;
}

export interface ReviewQueue {
  items: ReviewItem[];
}

export interface ReviewDecisionRequest {
  decision: Exclude<ReviewStatus, "pending">;
}

export interface ReviewDecisionResponse {
  item: ReviewItem;
  execution: Execution | null;
}

export interface ChatRequest {
  question: string;
}

export interface ChatResponse {
  intent: ChatIntent;
  answer: string;
  grounded_on: string[];
}

export interface ApiError {
  error: { code: string; message: string };
}
