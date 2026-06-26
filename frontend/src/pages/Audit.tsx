import { Download, Search, ShieldCheck } from 'lucide-react';
import { FC, useState, useMemo } from 'react';

import { useAuditLogs, useAuditIntegrity } from '../hooks/useAudit';
import { AuditFilters, AuditRecord, DecisionType } from '../types';

const decisionStyles: Record<string, string> = {
  approve: 'bg-green-100 text-green-800',
  verify: 'bg-yellow-100 text-yellow-800',
  block: 'bg-red-100 text-red-800',
};

const Audit: FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [decisionFilter, setDecisionFilter] = useState<'all' | DecisionType>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [integrityEnabled, setIntegrityEnabled] = useState(false);

  const filters: AuditFilters = useMemo(
    () => ({
      decision: decisionFilter === 'all' ? undefined : decisionFilter,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      limit: 1000,
      offset: 0,
    }),
    [decisionFilter, startDate, endDate]
  );

  const { data, isLoading, error } = useAuditLogs(filters);
  const { data: integrity, isFetching: integrityFetching } = useAuditIntegrity(integrityEnabled);

  // Transaction-ID search is client-side (the backend list endpoint has no tx filter).
  const filteredLogs = useMemo(() => {
    const items = data?.items ?? [];
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase();
    return items.filter((log) => log.transaction_id.toLowerCase().includes(q));
  }, [data, searchQuery]);

  const formatDate = (timestamp: string) =>
    new Date(timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

  const truncateHash = (hash: string) => (hash.length > 8 ? hash.slice(0, 8) + '...' : hash);

  const escapeCsv = (value: string) => {
    if (/[",\n]/.test(value)) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  };

  const handleExportCSV = () => {
    const headers = ['Date', 'Transaction', 'Decision', 'Score', 'Reason', 'Rules', 'Hash'];
    const rows = filteredLogs.map((log: AuditRecord) => [
      formatDate(log.created_at),
      log.transaction_id,
      log.decision,
      String(log.score),
      log.reason,
      log.rules_triggered.join('; '),
      log.hash,
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map((cell) => escapeCsv(String(cell))).join(','))
      .join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `audit-log-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="mt-1 text-sm text-gray-500">Review transaction decision history</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIntegrityEnabled(true)}
            disabled={integrityFetching}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <ShieldCheck className="h-4 w-4" />
            {integrityFetching ? 'Verifying...' : 'Verify Integrity'}
          </button>
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </div>
      </div>

      {integrityEnabled && integrity && (
        <div
          className={`rounded-md p-3 text-sm ${
            integrity.valid ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}
        >
          {integrity.message} ({integrity.total_records} records checked)
        </div>
      )}

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-1">
          <label htmlFor="audit-search" className="text-xs font-medium text-gray-500">
            Transaction ID
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              id="audit-search"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="rounded-md border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="audit-decision" className="text-xs font-medium text-gray-500">
            Decision
          </label>
          <select
            id="audit-decision"
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value as typeof decisionFilter)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="all">All</option>
            <option value="approve">Approve</option>
            <option value="verify">Verify</option>
            <option value="block">Block</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="audit-start" className="text-xs font-medium text-gray-500">
            From
          </label>
          <input
            id="audit-start"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="audit-end" className="text-xs font-medium text-gray-500">
            To
          </label>
          <input
            id="audit-end"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          Failed to load audit logs. Please try again.
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Transaction
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Decision
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Score
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Reason
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Hash
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-sm text-gray-500">
                    Loading audit logs...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-sm text-gray-500">
                    No audit logs found
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 font-mono text-sm font-medium text-gray-900">
                      {log.transaction_id}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                          decisionStyles[log.decision] || 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {log.decision}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {log.score}
                    </td>
                    <td className="max-w-xs truncate px-6 py-4 text-sm text-gray-500" title={log.reason}>
                      {log.reason}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 font-mono text-sm text-gray-500">
                      {truncateHash(log.hash)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Audit;
