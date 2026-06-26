import { isAxiosError } from 'axios';
import { Mail, MessageSquare, RefreshCw, Search, XCircle } from 'lucide-react';
import { FC, useMemo, useState } from 'react';

import {
  useDeliverOtp,
  useRejectVerification,
  useSubmitOtp,
  useVerificationQueue,
} from '../hooks/useVerifications';
import { VerificationState } from '../types';

const stateStyles: Record<VerificationState, string> = {
  PENDING: 'bg-yellow-100 text-yellow-800',
  VERIFIED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  EXPIRED: 'bg-gray-100 text-gray-800',
};

const STATES: VerificationState[] = ['PENDING', 'VERIFIED', 'FAILED', 'EXPIRED'];

const Verifications: FC = () => {
  const [stateFilter, setStateFilter] = useState<VerificationState>('PENDING');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [otpInputs, setOtpInputs] = useState<Record<string, string>>({});

  const { data, isLoading, isFetching, refetch, error } = useVerificationQueue(stateFilter);
  const deliverOtp = useDeliverOtp();
  const submitOtp = useSubmitOtp();
  const reject = useRejectVerification();

  const isAnyPending = deliverOtp.isPending || submitOtp.isPending || reject.isPending;

  const handleDeliverOtp = async (verificationId: string, channel: 'email' | 'sms') => {
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await deliverOtp.mutateAsync({ verificationId, channel });
      if (result.delivery_attempted) {
        setActionMessage(
          `OTP sent via ${channel} to ${result.contact_info ?? 'your contact on file'}.`
        );
      } else {
        setActionMessage(
          `OTP generated but delivery may have failed — check SMTP (email) or Twilio (SMS) settings in Azure.`
        );
      }
    } catch (err) {
      setActionError(
        isAxiosError(err)
          ? err.response?.data?.error?.message ?? err.message
          : `Failed to send ${channel} OTP.`
      );
    }
  };

  const handleSubmitOtp = async (verificationId: string) => {
    setActionError(null);
    setActionMessage(null);
    const otp = otpInputs[verificationId]?.trim();
    if (!otp) {
      setActionError('Enter the 6-digit OTP code.');
      return;
    }
    try {
      const result = await submitOtp.mutateAsync({ verificationId, otp });
      if (result.success) {
        setActionMessage(result.message);
        setOtpInputs((prev) => ({ ...prev, [verificationId]: '' }));
      } else {
        setActionError(result.message);
      }
    } catch (err) {
      setActionError(
        isAxiosError(err)
          ? err.response?.data?.error?.message ?? err.message
          : 'OTP verification failed.'
      );
    }
  };

  const handleReject = async (verificationId: string) => {
    setActionError(null);
    setActionMessage(null);
    try {
      await reject.mutateAsync(verificationId);
      setActionMessage('Transaction blocked after verification rejection.');
    } catch (err) {
      setActionError(
        isAxiosError(err) ? err.response?.data?.error?.message ?? err.message : 'Reject failed.'
      );
    }
  };

  const filtered = useMemo(() => {
    const source = data?.items ?? [];
    if (!searchQuery.trim()) return source;
    const q = searchQuery.toLowerCase();
    return source.filter(
      (v) =>
        v.verification_id.toLowerCase().includes(q) ||
        v.transaction_id.toLowerCase().includes(q) ||
        v.user_id.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const formatDate = (timestamp: string) =>
    new Date(timestamp).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  const formatAmount = (amount?: string | null, currency?: string | null) => {
    if (!amount) return '—';
    return `${currency ?? 'USD'} ${Number(amount).toLocaleString()}`;
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Verification Queue</h1>
          <p className="mt-1 text-sm text-gray-500">
            Medium-risk transactions (score 41–70) require OTP confirmation via email or SMS before
            approval.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {actionError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{actionError}</div>
      )}
      {actionMessage && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">{actionMessage}</div>
      )}
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          Failed to load the verification queue.
        </div>
      )}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by verification, transaction, or user ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-md border border-gray-300 py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value as VerificationState)}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0) + s.slice(1).toLowerCase()}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="text-gray-500">Loading verifications...</div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Transaction
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Amount
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Score
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    State
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    OTP
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-sm text-gray-500">
                      No verifications found. Submit a transaction that scores 41–70 (medium risk).
                    </td>
                  </tr>
                ) : (
                  filtered.map((v) => (
                    <tr key={v.verification_id} className="align-top hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <div className="font-mono text-xs text-gray-900">{v.transaction_id}</div>
                        <div className="mt-1 text-xs text-gray-500">
                          {formatDate(v.created_at)}
                        </div>
                        {v.channel && (
                          <div className="mt-1 text-xs text-gray-500">
                            Sent via {v.channel}
                            {v.contact_info ? ` → ${v.contact_info}` : ''}
                          </div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-900">
                        {formatAmount(v.amount, v.currency)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-900">
                        {v.risk_score ?? '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                            stateStyles[v.state] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {v.state.toLowerCase()}
                        </span>
                        <div className="mt-1 text-xs text-gray-500">
                          {v.attempts}/{v.max_attempts} attempts
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        {v.state === 'PENDING' ? (
                          <div className="flex flex-col gap-2">
                            <div className="flex flex-wrap gap-1.5">
                              <button
                                onClick={() => handleDeliverOtp(v.verification_id, 'email')}
                                disabled={isAnyPending}
                                className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                              >
                                <Mail className="h-3.5 w-3.5" />
                                Email OTP
                              </button>
                              <button
                                onClick={() => handleDeliverOtp(v.verification_id, 'sms')}
                                disabled={isAnyPending}
                                className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                              >
                                <MessageSquare className="h-3.5 w-3.5" />
                                SMS OTP
                              </button>
                            </div>
                            <div className="flex gap-1.5">
                              <input
                                type="text"
                                inputMode="numeric"
                                maxLength={6}
                                placeholder="6-digit code"
                                value={otpInputs[v.verification_id] ?? ''}
                                onChange={(e) =>
                                  setOtpInputs((prev) => ({
                                    ...prev,
                                    [v.verification_id]: e.target.value.replace(/\D/g, ''),
                                  }))
                                }
                                className="w-28 rounded-md border border-gray-300 px-2 py-1 text-sm"
                              />
                              <button
                                onClick={() => handleSubmitOtp(v.verification_id)}
                                disabled={isAnyPending}
                                className="rounded-md bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                              >
                                Verify
                              </button>
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4">
                        {v.state === 'PENDING' && (
                          <button
                            onClick={() => handleReject(v.verification_id)}
                            disabled={isAnyPending}
                            className="inline-flex items-center gap-1 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                            title="Block this transaction"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            Block
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Verifications;
