export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string | null;
  role: string;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type DecisionType = 'approve' | 'verify' | 'block';

/**
 * Audit record as returned by GET /api/v1/audit and GET /api/v1/audit/{transaction_id}.
 * `created_at` is a date string (YYYY-MM-DD) per the backend AuditRecordResponse.
 */
export interface AuditRecord {
  id: string;
  transaction_id: string;
  decision: DecisionType;
  score: number;
  reason: string;
  features: Record<string, unknown>;
  rules_triggered: string[];
  model_version: string | null;
  hash: string;
  previous_hash: string | null;
  created_at: string;
}

/** Decision returned by GET /api/v1/decisions/{transaction_id}. */
export interface Decision {
  transaction_id: string;
  score: number;
  decision: DecisionType;
  reason: string;
  rules_triggered: string[];
  features_used: Record<string, unknown>;
  created_at: string;
  model_version?: string | null;
}

export interface AuditFilters {
  decision?: DecisionType;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

/** Transaction row from GET /api/v1/transactions. */
export interface TransactionSummary {
  transaction_id: string;
  amount: number;
  currency: string;
  decision: DecisionType;
  score: number;
  reason: string;
  rules_triggered: string[];
  created_at: string;
}

export interface TransactionListResponse {
  total: number;
  limit: number;
  offset: number;
  items: TransactionSummary[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface IntegrityResult {
  valid: boolean;
  total_records: number;
  first_broken_id: string | null;
  message: string;
}

/** Dashboard metrics from GET /api/v1/dashboard/metrics. */
export interface FraudTrendPoint {
  date: string;
  total: number;
  blocked: number;
}

export interface DashboardMetrics {
  total_transactions: number;
  blocked_transactions: number;
  high_risk_users: number;
  false_positive_rate: number;
  fraud_trends: FraudTrendPoint[];
}

/** Fraud rule contracts for /api/v1/rules. */
export interface Rule {
  id: string;
  name: string;
  description: string | null;
  rule_type: string;
  conditions: Record<string, unknown> | null;
  action: string;
  priority: number;
  score_value: number;
  is_active: boolean;
  created_at: string;
}

export interface RuleCreatePayload {
  name: string;
  description?: string | null;
  rule_type: string;
  conditions: Record<string, unknown>;
  action: string;
  priority: number;
  score_value?: number | null;
}

export type RuleUpdatePayload = Partial<RuleCreatePayload>;

/** Verification queue contracts for /api/v1/verify. */
export type VerificationState = 'PENDING' | 'VERIFIED' | 'FAILED' | 'EXPIRED';

export interface VerificationQueueItem {
  verification_id: string;
  transaction_id: string;
  user_id: string;
  state: VerificationState;
  channel: string | null;
  contact_info: string | null;
  attempts: number;
  max_attempts: number;
  created_at: string;
  expires_at: string | null;
  amount?: string | null;
  currency?: string | null;
  transaction_status?: string | null;
  risk_score?: number | null;
}

export interface VerificationQueueResponse {
  total: number;
  limit: number;
  offset: number;
  items: VerificationQueueItem[];
}

/** Generic wrapper used by the /verify endpoints: { success, data } / { success, error }. */
export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

/** Alert contracts for /api/v1/alerts. */
export interface Alert {
  id: string;
  transaction_id: string;
  user_id: string;
  alert_type: string;
  severity: string;
  status: string;
  assigned_to: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface AlertListResponse {
  total: number;
  limit: number;
  offset: number;
  items: Alert[];
}

export interface AlertFilters {
  status?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}

/** Transaction ingestion contracts for POST /api/v1/transactions. */
export interface TransactionSubmitRequest {
  user_id: string;
  amount: number;
  currency: string;
  merchant_id?: string | null;
  merchant_category?: string | null;
  location?: string | null;
  device_id?: string | null;
  ip_address?: string | null;
  card_last_four?: string | null;
  payment_method?: string | null;
  transaction_time?: string | null;
}

export interface TransactionDecisionResponse {
  transaction_id: string;
  decision: DecisionType;
  score: number;
  reason: string;
  rules_triggered: string[];
  requires_verification: boolean;
}

/** Decision override contracts for /api/v1/decisions/{transaction_id}/override. */
export interface DecisionOverrideRequest {
  new_decision: string;
  reason: string;
}

export interface DecisionOverrideResponse {
  transaction_id: string;
  old_decision: string;
  new_decision: string;
  reason: string;
  audit_id: string | null;
}
