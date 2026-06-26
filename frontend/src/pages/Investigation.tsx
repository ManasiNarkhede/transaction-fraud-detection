import { isAxiosError } from 'axios';
import { ArrowLeft, ShieldAlert, RotateCcw } from 'lucide-react';
import { FC, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { useDecisionOverride, useDecisionRecord } from '../hooks/useDecisions';

const getScoreColor = (score: number): string => {
  if (score <= 40) return 'text-green-600';
  if (score <= 70) return 'text-yellow-600';
  return 'text-red-600';
};

const getScoreBgColor = (score: number): string => {
  if (score <= 40) return 'bg-green-50';
  if (score <= 70) return 'bg-yellow-50';
  return 'bg-red-50';
};

const getRiskLevel = (score: number): string => {
  if (score <= 40) return 'LOW';
  if (score <= 70) return 'MEDIUM';
  return 'HIGH';
};

const getRiskBadgeColor = (score: number): string => {
  if (score <= 40) return 'bg-green-100 text-green-800';
  if (score <= 70) return 'bg-yellow-100 text-yellow-800';
  return 'bg-red-100 text-red-800';
};

const getDecisionBadgeColor = (decision: string): string => {
  switch (decision) {
    case 'approve':
      return 'bg-green-100 text-green-800';
    case 'verify':
      return 'bg-yellow-100 text-yellow-800';
    case 'block':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

const formatFeatureValue = (value: unknown): string => {
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const DECISION_OPTIONS = ['approve', 'verify', 'block'];

const Investigation: FC = () => {
  const { transactionId } = useParams<{ transactionId: string }>();
  const navigate = useNavigate();
  const { data, isLoading, error } = useDecisionRecord(transactionId);
  const overrideMutation = useDecisionOverride();

  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [newDecision, setNewDecision] = useState('approve');
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideError, setOverrideError] = useState<string | null>(null);
  const [overrideSuccess, setOverrideSuccess] = useState<string | null>(null);

  const handleBack = () => navigate(-1);

  const featureEntries = data ? Object.entries(data.features_used ?? {}) : [];

  const handleOverride = async () => {
    if (!transactionId) return;
    if (!overrideReason.trim()) {
      setOverrideError('A reason is required.');
      return;
    }
    setOverrideError(null);
    setOverrideSuccess(null);
    try {
      const result = await overrideMutation.mutateAsync({
        transactionId,
        payload: { new_decision: newDecision, reason: overrideReason.trim() },
      });
      setOverrideSuccess(
        `Override applied: ${result.old_decision} → ${result.new_decision}. Audit ID: ${result.audit_id ?? 'n/a'}`
      );
      setShowOverrideForm(false);
      setOverrideReason('');
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 403) {
        setOverrideError('Admin privileges are required to override decisions.');
      } else {
        setOverrideError('Failed to apply override. Please try again.');
      }
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-4">
        <button
          onClick={handleBack}
          className="flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Investigation</h1>
          <p className="mt-1 text-sm text-gray-500">
            Transaction ID: <span className="font-mono font-medium">{transactionId}</span>
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="flex h-32 items-center justify-center text-gray-500">
          Loading investigation...
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          Could not load this transaction. It may not exist or may not belong to your account.
        </div>
      )}

      {data && (
        <>
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-900">Risk Assessment</h2>
              <div className="mt-4 flex flex-col items-center gap-4 sm:flex-row sm:gap-8">
                <div
                  className={`flex h-32 w-32 items-center justify-center rounded-full ${getScoreBgColor(data.score)}`}
                >
                  <span className={`text-5xl font-bold ${getScoreColor(data.score)}`}>
                    {data.score}
                  </span>
                </div>
                <div className="flex flex-col items-center gap-2 sm:items-start">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-500">Risk Level:</span>
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold uppercase ${getRiskBadgeColor(data.score)}`}
                    >
                      {getRiskLevel(data.score)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-500">Decision:</span>
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold uppercase ${getDecisionBadgeColor(data.decision)}`}
                    >
                      {data.decision}
                    </span>
                  </div>
                  {data.model_version && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-500">Model:</span>
                      <span className="text-sm text-gray-700">{data.model_version}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-900">Decision Rationale</h2>
              <div className="mt-4 rounded-md bg-gray-50 p-4">
                <p className="text-sm text-gray-700">{data.reason}</p>
              </div>
              {data.rules_triggered.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-medium text-gray-500">Rules Triggered</h3>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {data.rules_triggered.map((rule) => (
                      <span
                        key={rule}
                        className="inline-flex rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700"
                      >
                        {rule}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-900">Feature Breakdown</h2>
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Feature
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {featureEntries.length === 0 ? (
                      <tr>
                        <td colSpan={2} className="px-6 py-6 text-center text-sm text-gray-500">
                          No features recorded
                        </td>
                      </tr>
                    ) : (
                      featureEntries.map(([name, value]) => (
                        <tr key={name} className="hover:bg-gray-50">
                          <td className="whitespace-nowrap px-6 py-4 font-mono text-sm font-medium text-gray-900">
                            {name}
                          </td>
                          <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                            {formatFeatureValue(value)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Decision Override Panel (admin only) */}
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-5 w-5 text-gray-500" />
                  <h2 className="text-lg font-semibold text-gray-900">Decision Override</h2>
                </div>
                {!showOverrideForm && (
                  <button
                    onClick={() => {
                      setShowOverrideForm(true);
                      setOverrideError(null);
                      setOverrideSuccess(null);
                    }}
                    className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Override Decision
                  </button>
                )}
              </div>

              {overrideSuccess && (
                <div className="mt-4 rounded-md bg-green-50 p-3 text-sm text-green-700">
                  {overrideSuccess}
                </div>
              )}

              {!showOverrideForm && !overrideSuccess && (
                <p className="mt-3 text-sm text-gray-500">
                  Admin only. Overriding appends an immutable audit entry and updates the
                  transaction status.
                </p>
              )}

              {showOverrideForm && (
                <div className="mt-4 space-y-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-medium text-gray-500">New Decision</label>
                    <select
                      value={newDecision}
                      onChange={(e) => setNewDecision(e.target.value)}
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      {DECISION_OPTIONS.map((d) => (
                        <option key={d} value={d}>
                          {d.charAt(0).toUpperCase() + d.slice(1)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-medium text-gray-500">Reason (required)</label>
                    <textarea
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      rows={3}
                      placeholder="Explain why this decision is being overridden..."
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>

                  {overrideError && (
                    <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                      {overrideError}
                    </div>
                  )}

                  <div className="flex justify-end gap-3">
                    <button
                      onClick={() => {
                        setShowOverrideForm(false);
                        setOverrideReason('');
                        setOverrideError(null);
                      }}
                      className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleOverride}
                      disabled={overrideMutation.isPending}
                      className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {overrideMutation.isPending ? 'Applying...' : 'Apply Override'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Investigation;
