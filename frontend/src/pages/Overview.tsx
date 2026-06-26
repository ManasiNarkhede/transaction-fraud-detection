import { Activity, Ban, Users, Percent } from 'lucide-react';
import { FC, useMemo, useState } from 'react';

import KPICard from '../components/KPICard';
import RiskChart from '../components/RiskChart';
import TransactionTable, { TxSortField, SortDirection } from '../components/TransactionTable';
import { useDashboardMetrics } from '../hooks/useDashboard';
import { useTransactions } from '../hooks/useTransactions';

const Overview: FC = () => {
  const { data: metrics, isLoading: metricsLoading, error: metricsError } = useDashboardMetrics();

  const { data: txData, isLoading: txLoading } = useTransactions({ limit: 10, offset: 0 });

  const [sortField, setSortField] = useState<TxSortField>('created_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = (field: TxSortField) => {
    if (field === sortField) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const recentTransactions = useMemo(() => {
    const items = txData?.items ?? [];
    return items
      .map((tx) => ({
        id: tx.transaction_id,
        transaction_id: tx.transaction_id,
        decision: tx.decision,
        score: tx.score,
        reason: tx.reason,
        rules_triggered: tx.rules_triggered,
        created_at: tx.created_at,
        features: {},
        model_version: null,
        hash: '',
        previous_hash: null,
      }))
      .slice()
      .sort((a, b) => {
      const modifier = sortDirection === 'asc' ? 1 : -1;
      if (sortField === 'score') {
        return (a.score - b.score) * modifier;
      }
      return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * modifier;
    });
  }, [txData, sortField, sortDirection]);

  if (metricsLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  const falsePositivePct =
    metrics != null ? `${(metrics.false_positive_rate * 100).toFixed(1)}%` : '—';

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Overview</h1>
        <p className="mt-1 text-sm text-gray-500">Real-time fraud detection metrics</p>
      </div>

      {metricsError && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          Failed to load dashboard metrics. Please try again.
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard
          title="Total Transactions"
          value={metrics?.total_transactions ?? 0}
          subtitle="All time"
          icon={<Activity className="h-6 w-6" />}
          color="bg-blue-500"
        />
        <KPICard
          title="Blocked Transactions"
          value={metrics?.blocked_transactions ?? 0}
          subtitle="Fraud detected"
          icon={<Ban className="h-6 w-6" />}
          color="bg-red-500"
        />
        <KPICard
          title="High-Risk Users"
          value={metrics?.high_risk_users ?? 0}
          subtitle="Above score threshold"
          icon={<Users className="h-6 w-6" />}
          color="bg-amber-500"
        />
        <KPICard
          title="False-Positive Rate"
          value={falsePositivePct}
          subtitle="Verified legitimate / terminal"
          icon={<Percent className="h-6 w-6" />}
          color="bg-indigo-500"
        />
      </div>

      <RiskChart data={metrics?.fraud_trends ?? []} />

      <div>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Recent Decisions</h2>
        {txLoading ? (
          <div className="flex h-32 items-center justify-center text-gray-500">
            Loading recent decisions...
          </div>
        ) : (
          <TransactionTable
            transactions={recentTransactions}
            onSort={handleSort}
            sortField={sortField}
            sortDirection={sortDirection}
          />
        )}
      </div>
    </div>
  );
};

export default Overview;
