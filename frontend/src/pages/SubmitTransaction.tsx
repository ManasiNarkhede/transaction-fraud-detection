import { AxiosError } from 'axios';
import { CheckCircle, AlertTriangle, XCircle, Play, Send, RotateCcw } from 'lucide-react';
import { FC, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { transactionsApi } from '../api/transactions';
import { LabelWithTooltip } from '../components/InfoTooltip';
import { SUBMIT_TRANSACTION_FIELD_HELP } from '../constants/fieldHelp';
import { useSubmitTransaction } from '../hooks/useSubmitTransaction';
import { useAuthStore } from '../stores/authStore';
import { TransactionDecisionResponse, TransactionSubmitRequest, DecisionType } from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF'];
const PAYMENT_METHODS = ['card', 'wallet', 'transfer', 'crypto', 'bnpl'];
const MERCHANT_CATEGORIES = [
  'retail',
  'food_beverage',
  'travel',
  'entertainment',
  'electronics',
  'jewelry',
  'gambling',
  'crypto_exchange',
  'other',
];

const SIMULATE_COUNT = 10;

interface SimulationSummary {
  approve: number;
  verify: number;
  block: number;
  total: number;
}

function randomBetween(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

function randomFrom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function buildRandomPayload(userId: string): TransactionSubmitRequest {
  const highRisk = Math.random() < 0.3;
  return {
    user_id: userId,
    amount: highRisk
      ? parseFloat(randomBetween(3000, 15000).toFixed(2))
      : parseFloat(randomBetween(5, 500).toFixed(2)),
    currency: randomFrom(CURRENCIES),
    merchant_id: `MERCH-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    merchant_category: highRisk
      ? randomFrom(['crypto_exchange', 'gambling', 'jewelry'])
      : randomFrom(['retail', 'food_beverage', 'travel']),
    location: randomFrom(['US', 'GB', 'DE', 'NG', 'RU', 'CN', 'BR', 'AU']),
    device_id: `DEV-${Math.random().toString(36).slice(2, 10)}`,
    ip_address: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
    card_last_four: String(Math.floor(Math.random() * 9000) + 1000),
    payment_method: randomFrom(PAYMENT_METHODS),
  };
}

// ---------------------------------------------------------------------------
// Decision badge
// ---------------------------------------------------------------------------

interface DecisionBadgeProps {
  decision: DecisionType;
}

const DECISION_CONFIG: Record<
  DecisionType,
  { label: string; bg: string; text: string; border: string; icon: FC<{ className?: string }> }
> = {
  approve: {
    label: 'APPROVED',
    bg: 'bg-green-50',
    text: 'text-green-800',
    border: 'border-green-200',
    icon: CheckCircle,
  },
  verify: {
    label: 'VERIFY',
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
    icon: AlertTriangle,
  },
  block: {
    label: 'BLOCKED',
    bg: 'bg-red-50',
    text: 'text-red-800',
    border: 'border-red-200',
    icon: XCircle,
  },
};

const DecisionBadge: FC<DecisionBadgeProps> = ({ decision }) => {
  const cfg = DECISION_CONFIG[decision] ?? DECISION_CONFIG['block'];
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-semibold ${cfg.bg} ${cfg.text} ${cfg.border}`}
    >
      <Icon className="h-4 w-4" />
      {cfg.label}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Decision result card
// ---------------------------------------------------------------------------

interface DecisionResultProps {
  result: TransactionDecisionResponse;
}

const DecisionResult: FC<DecisionResultProps> = ({ result }) => {
  const cfg = DECISION_CONFIG[result.decision] ?? DECISION_CONFIG['block'];
  return (
    <div className={`rounded-lg border-2 p-5 ${cfg.border} ${cfg.bg}`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className={`text-lg font-bold ${cfg.text}`}>Decision Result</h3>
        <DecisionBadge decision={result.decision} />
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="font-medium text-gray-600">Transaction ID</dt>
          <dd className="mt-0.5 font-mono text-xs text-gray-800 break-all">
            {result.transaction_id}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-gray-600">Risk Score</dt>
          <dd className={`mt-0.5 text-2xl font-bold ${cfg.text}`}>{result.score}</dd>
        </div>
        <div className="col-span-2">
          <dt className="font-medium text-gray-600">Reason</dt>
          <dd className="mt-0.5 text-gray-800">{result.reason}</dd>
        </div>
        {result.rules_triggered.length > 0 && (
          <div className="col-span-2">
            <dt className="font-medium text-gray-600">Rules Triggered</dt>
            <dd className="mt-1 flex flex-wrap gap-1">
              {result.rules_triggered.map((r) => (
                <span
                  key={r}
                  className="rounded bg-white/70 px-2 py-0.5 font-mono text-xs text-gray-700 ring-1 ring-gray-300"
                >
                  {r}
                </span>
              ))}
            </dd>
          </div>
        )}
        {result.requires_verification && (
          <div className="col-span-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
              <AlertTriangle className="h-3 w-3" />
              Requires additional verification
            </span>
          </div>
        )}
      </dl>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Simulate progress
// ---------------------------------------------------------------------------

interface SimulateProgressProps {
  current: number;
  total: number;
  summary: SimulationSummary;
}

const SimulateProgress: FC<SimulateProgressProps> = ({ current, total, summary }) => {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
      <div className="mb-2 flex items-center justify-between text-sm font-medium text-indigo-800">
        <span>Simulating transactions…</span>
        <span>
          {current} / {total}
        </span>
      </div>
      <div className="mb-3 h-2 overflow-hidden rounded-full bg-indigo-200">
        <div
          className="h-full rounded-full bg-indigo-600 transition-all duration-200"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex gap-4 text-sm">
        <span className="font-semibold text-green-700">✓ {summary.approve} approved</span>
        <span className="font-semibold text-amber-700">⚠ {summary.verify} verify</span>
        <span className="font-semibold text-red-700">✗ {summary.block} blocked</span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Simulate summary (done)
// ---------------------------------------------------------------------------

interface SimulateSummaryCardProps {
  summary: SimulationSummary;
  onDismiss: () => void;
}

const SimulateSummaryCard: FC<SimulateSummaryCardProps> = ({ summary, onDismiss }) => (
  <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
    <div className="mb-3 flex items-center justify-between">
      <h3 className="font-semibold text-gray-900">Simulation Complete</h3>
      <button
        onClick={onDismiss}
        className="text-xs text-gray-500 underline hover:text-gray-700"
      >
        Dismiss
      </button>
    </div>
    <div className="grid grid-cols-3 gap-3 text-center">
      <div className="rounded-md bg-green-50 p-3">
        <div className="text-2xl font-bold text-green-700">{summary.approve}</div>
        <div className="text-xs text-green-600">Approved</div>
      </div>
      <div className="rounded-md bg-amber-50 p-3">
        <div className="text-2xl font-bold text-amber-700">{summary.verify}</div>
        <div className="text-xs text-amber-600">Verify</div>
      </div>
      <div className="rounded-md bg-red-50 p-3">
        <div className="text-2xl font-bold text-red-700">{summary.block}</div>
        <div className="text-xs text-red-600">Blocked</div>
      </div>
    </div>
    <p className="mt-3 text-xs text-gray-500">
      {summary.total} transactions sent. Dashboard metrics have been refreshed.
    </p>
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

interface FormFields {
  user_id: string;
  amount: string;
  currency: string;
  merchant_id: string;
  merchant_category: string;
  location: string;
  device_id: string;
  ip_address: string;
  card_last_four: string;
  payment_method: string;
}

function emptyForm(userId: string): FormFields {
  return {
    user_id: userId,
    amount: '',
    currency: 'INR',
    merchant_id: '',
    merchant_category: '',
    location: '',
    device_id: '',
    ip_address: '',
    card_last_four: '',
    payment_method: '',
  };
}

function buildPayload(f: FormFields, accountId: string): TransactionSubmitRequest {
  const payload: TransactionSubmitRequest = {
    user_id: accountId,
    amount: parseFloat(parseFloat(f.amount).toFixed(2)),
    currency: f.currency.trim().toUpperCase(),
  };
  if (f.merchant_id.trim()) payload.merchant_id = f.merchant_id.trim();
  if (f.merchant_category.trim()) payload.merchant_category = f.merchant_category.trim();
  if (f.location.trim()) payload.location = f.location.trim();
  if (f.device_id.trim()) payload.device_id = f.device_id.trim();
  if (f.ip_address.trim()) payload.ip_address = f.ip_address.trim();
  if (f.card_last_four.trim()) payload.card_last_four = f.card_last_four.trim();
  if (f.payment_method.trim()) payload.payment_method = f.payment_method.trim();
  return payload;
}

function validate(f: FormFields, accountId: string): string | null {
  if (!accountId) return 'You must be signed in to submit a transaction.';
  const uuid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuid.test(accountId)) return 'Invalid account session.';
  const amt = parseFloat(f.amount);
  if (!f.amount || isNaN(amt) || amt <= 0) return 'Amount must be a positive number.';
  if (!f.currency.trim() || f.currency.trim().length !== 3)
    return 'Currency must be a 3-letter code (e.g. USD).';
  if (f.card_last_four.trim() && !/^\d{4}$/.test(f.card_last_four.trim()))
    return 'Card last four must be exactly 4 digits.';
  return null;
}

const SubmitTransaction: FC = () => {
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();

  const [form, setForm] = useState<FormFields>(() => emptyForm(user?.id ?? ''));
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<TransactionDecisionResponse | null>(null);

  // Simulation state
  const [simRunning, setSimRunning] = useState(false);
  const [simProgress, setSimProgress] = useState(0);
  const [simSummary, setSimSummary] = useState<SimulationSummary | null>(null);
  const [simDone, setSimDone] = useState(false);

  const { mutate, isPending } = useSubmitTransaction();

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const { name, value } = e.target;
      setForm((prev) => ({ ...prev, [name]: value }));
      setValidationError(null);
    },
    []
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate(form, user?.id ?? '');
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(null);
    setApiError(null);
    setLastResult(null);
    mutate(buildPayload(form, user?.id ?? ''), {
      onSuccess: (data) => {
        setLastResult(data);
      },
      onError: (error) => {
        const axiosErr = error as AxiosError<{ detail?: string | { msg: string }[] }>;
        const detail = axiosErr.response?.data?.detail;
        if (typeof detail === 'string') {
          setApiError(detail);
        } else if (Array.isArray(detail)) {
          setApiError(detail.map((d) => d.msg).join('; '));
        } else {
          setApiError(
            axiosErr.response?.status
              ? `Request failed (${axiosErr.response.status})`
              : 'The request timed out, but your transaction may still have been processed. Check Transactions or Overview.'
          );
        }
      },
    });
  };

  const handleReset = () => {
    setForm(emptyForm(user?.id ?? ''));
    setValidationError(null);
    setApiError(null);
    setLastResult(null);
  };

  const handleSimulate = useCallback(async () => {
    if (simRunning) return;
    const userId = user?.id;
    if (!userId) {
      setValidationError('You must be signed in to simulate.');
      return;
    }

    setSimRunning(true);
    setSimDone(false);
    setSimProgress(0);
    setSimSummary({ approve: 0, verify: 0, block: 0, total: 0 });
    setLastResult(null);
    setApiError(null);

    const tally = { approve: 0, verify: 0, block: 0, total: 0 };

    for (let i = 0; i < SIMULATE_COUNT; i++) {
      try {
        const res = await transactionsApi.submit(buildRandomPayload(userId));
        tally[res.decision] = (tally[res.decision] ?? 0) + 1;
        tally.total += 1;
      } catch {
        // Count silent failures toward total but not a decision
        tally.total += 1;
      }
      setSimProgress(i + 1);
      setSimSummary({ ...tally });
    }

    setSimRunning(false);
    setSimDone(true);
  }, [simRunning, user?.id]);

  const inputBase =
    'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500';

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Submit Transaction</h1>
        <p className="mt-1 text-sm text-gray-500">
          Send a live transaction for real-time fraud scoring, or simulate a batch.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ---- Form ---- */}
        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-900">Transaction Details</h2>

          {/* Required fields */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <LabelWithTooltip
                htmlFor="user_id"
                label="Your Account ID"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.user_id}
                required
              />
              <input
                id="user_id"
                name="user_id"
                type="text"
                className={`${inputBase} bg-gray-50`}
                value={user?.id ?? form.user_id}
                readOnly
                aria-readonly="true"
              />
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="amount"
                label="Amount"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.amount}
                required
              />
              <input
                id="amount"
                name="amount"
                type="number"
                step="0.01"
                min="0.01"
                className={inputBase}
                placeholder="0.00"
                value={form.amount}
                onChange={handleChange}
                required
              />
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="currency"
                label="Currency"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.currency}
                required
              />
              <select
                id="currency"
                name="currency"
                className={inputBase}
                value={form.currency}
                onChange={handleChange}
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Optional fields */}
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Optional Context
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <LabelWithTooltip
                htmlFor="merchant_id"
                label="Merchant ID"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.merchant_id}
              />
              <input
                id="merchant_id"
                name="merchant_id"
                type="text"
                className={inputBase}
                placeholder="MERCH-XYZ"
                value={form.merchant_id}
                onChange={handleChange}
              />
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="merchant_category"
                label="Merchant Category"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.merchant_category}
              />
              <select
                id="merchant_category"
                name="merchant_category"
                className={inputBase}
                value={form.merchant_category}
                onChange={handleChange}
              >
                <option value="">— Select —</option>
                {MERCHANT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="location"
                label="Location / Country"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.location}
              />
              <input
                id="location"
                name="location"
                type="text"
                className={inputBase}
                placeholder="US"
                value={form.location}
                onChange={handleChange}
              />
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="payment_method"
                label="Payment Method"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.payment_method}
              />
              <select
                id="payment_method"
                name="payment_method"
                className={inputBase}
                value={form.payment_method}
                onChange={handleChange}
              >
                <option value="">— Select —</option>
                {PAYMENT_METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="device_id"
                label="Device ID"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.device_id}
              />
              <input
                id="device_id"
                name="device_id"
                type="text"
                className={inputBase}
                placeholder="DEV-abc123"
                value={form.device_id}
                onChange={handleChange}
              />
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="ip_address"
                label="IP Address"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.ip_address}
              />
              <input
                id="ip_address"
                name="ip_address"
                type="text"
                className={inputBase}
                placeholder="192.168.1.1"
                value={form.ip_address}
                onChange={handleChange}
              />
            </div>

            <div>
              <LabelWithTooltip
                htmlFor="card_last_four"
                label="Card Last 4"
                tooltip={SUBMIT_TRANSACTION_FIELD_HELP.card_last_four}
              />
              <input
                id="card_last_four"
                name="card_last_four"
                type="text"
                maxLength={4}
                className={inputBase}
                placeholder="1234"
                value={form.card_last_four}
                onChange={handleChange}
              />
            </div>
          </div>

          {/* Errors */}
          {validationError && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{validationError}</p>
          )}
          {apiError && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{apiError}</p>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Send className="h-4 w-4" />
              {isPending ? 'Submitting…' : 'Submit Transaction'}
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              <RotateCcw className="h-4 w-4" />
              Reset
            </button>
          </div>

          {/* Simulate */}
          <div className="border-t border-gray-100 pt-4">
            <p className="mb-2 text-xs text-gray-500">
              Simulate {SIMULATE_COUNT} randomised transactions (varied amount, merchant, location)
              to generate a mix of decisions. Uses your account.
            </p>
            <button
              type="button"
              onClick={handleSimulate}
              disabled={simRunning || isPending}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {simRunning ? 'Running simulation…' : `Simulate ${SIMULATE_COUNT} Transactions`}
            </button>
          </div>
        </form>

        {/* ---- Right panel: result + simulation progress ---- */}
        <div className="space-y-4">
          {/* Single submit result */}
          {lastResult && <DecisionResult result={lastResult} />}

          {/* No result placeholder */}
          {!lastResult && !simRunning && !simDone && (
            <div className="flex h-40 flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-200 text-gray-400">
              <Send className="mb-2 h-8 w-8" />
              <p className="text-sm">Submit a transaction to see the real-time decision here.</p>
            </div>
          )}

          {/* Simulation in progress */}
          {simRunning && simSummary && (
            <SimulateProgress
              current={simProgress}
              total={SIMULATE_COUNT}
              summary={simSummary}
            />
          )}

          {/* Simulation complete */}
          {simDone && simSummary && (
            <SimulateSummaryCard
              summary={simSummary}
              onDismiss={() => {
                setSimDone(false);
                setSimSummary(null);
              }}
            />
          )}

          {/* Quick link to investigation */}
          {lastResult && (
            <button
              onClick={() => navigate(`/investigation/${lastResult.transaction_id}`)}
              className="w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              View Investigation for this transaction →
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SubmitTransaction;
