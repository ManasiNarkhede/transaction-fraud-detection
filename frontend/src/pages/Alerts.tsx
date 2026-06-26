import {
  RefreshCw,
  Search,
  AlertTriangle,
  ShieldAlert,
  Shield,
  Info,
  ExternalLink,
  CheckCheck,
  CheckCircle,
} from 'lucide-react';
import { FC, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAlerts, useAcknowledgeAlert, useResolveAlert } from '../hooks/useAlerts';

type Severity = 'critical' | 'high' | 'medium' | 'low';
type StatusFilter = 'all' | 'open' | 'investigating' | 'resolved' | 'dismissed';

const severityStyles: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-blue-100 text-blue-800',
};

const severityIcon = (severity: string): React.ReactNode => {
  switch (severity) {
    case 'critical':
      return <ShieldAlert className="h-4 w-4" />;
    case 'high':
      return <AlertTriangle className="h-4 w-4" />;
    case 'medium':
      return <Shield className="h-4 w-4" />;
    default:
      return <Info className="h-4 w-4" />;
  }
};

const statusStyles: Record<string, string> = {
  open: 'bg-red-100 text-red-800',
  investigating: 'bg-yellow-100 text-yellow-800',
  resolved: 'bg-green-100 text-green-800',
  dismissed: 'bg-gray-100 text-gray-800',
};

const SEVERITIES: Array<{ value: Severity | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const STATUSES: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'investigating', label: 'Investigating' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'dismissed', label: 'Dismissed' },
];

const Alerts: FC = () => {
  const navigate = useNavigate();

  const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const alertFilters = {
    severity: severityFilter !== 'all' ? severityFilter : undefined,
    status: statusFilter !== 'all' ? statusFilter : undefined,
    limit: 200,
    offset: 0,
  };

  const { data, isLoading, isFetching, refetch, error } = useAlerts(alertFilters);
  const acknowledge = useAcknowledgeAlert();
  const resolve = useResolveAlert();

  const isAnyPending = acknowledge.isPending || resolve.isPending;

  const handleAction = async (action: 'acknowledge' | 'resolve', alertId: string) => {
    setActionError(null);
    try {
      if (action === 'acknowledge') await acknowledge.mutateAsync(alertId);
      else await resolve.mutateAsync(alertId);
    } catch {
      setActionError(`Failed to ${action} alert.`);
    }
  };

  const filteredItems = (data?.items ?? []).filter((alert) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      alert.transaction_id.toLowerCase().includes(q) ||
      alert.id.toLowerCase().includes(q) ||
      alert.alert_type.toLowerCase().includes(q)
    );
  });

  const formatDate = (timestamp: string) =>
    new Date(timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alert Queue</h1>
          <p className="mt-1 text-sm text-gray-500">
            Fraud alerts — acknowledge to investigate, resolve when actioned
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
      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          Failed to load alerts. Please try again.
        </div>
      )}

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-1">
          <label htmlFor="severity-filter" className="text-xs font-medium text-gray-500">
            Severity
          </label>
          <select
            id="severity-filter"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as Severity | 'all')}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {SEVERITIES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="status-filter" className="text-xs font-medium text-gray-500">
            Status
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {STATUSES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="search-input" className="text-xs font-medium text-gray-500">
            Search
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              id="search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Transaction ID, alert type..."
              className="rounded-md border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="text-gray-500">Loading alerts...</div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Severity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Transaction
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-sm text-gray-500">
                      No alerts found
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((alert) => (
                    <tr key={alert.id} className="hover:bg-gray-50">
                      <td className="whitespace-nowrap px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                            severityStyles[alert.severity] ?? 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {severityIcon(alert.severity)}
                          {alert.severity}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-700">
                        {alert.alert_type}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 font-mono text-sm font-medium text-gray-900">
                        {alert.transaction_id}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                            statusStyles[alert.status] ?? 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {alert.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                        {formatDate(alert.created_at)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex items-center gap-1.5">
                          {alert.status === 'open' && (
                            <button
                              onClick={() => handleAction('acknowledge', alert.id)}
                              disabled={isAnyPending}
                              className="inline-flex items-center gap-1 rounded-md bg-yellow-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-yellow-700 disabled:opacity-50"
                              title="Acknowledge — mark as investigating"
                            >
                              <CheckCheck className="h-3.5 w-3.5" />
                              Acknowledge
                            </button>
                          )}
                          {(alert.status === 'open' || alert.status === 'investigating') && (
                            <button
                              onClick={() => handleAction('resolve', alert.id)}
                              disabled={isAnyPending}
                              className="inline-flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                              title="Resolve alert"
                            >
                              <CheckCircle className="h-3.5 w-3.5" />
                              Resolve
                            </button>
                          )}
                          <button
                            onClick={() => navigate(`/investigation/${alert.transaction_id}`)}
                            className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                          >
                            <ExternalLink className="h-3 w-3" />
                            Investigate
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {data && (
            <div className="border-t border-gray-200 px-6 py-3 text-xs text-gray-500">
              Showing {filteredItems.length} of {data.total} alerts
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Alerts;
