import { ChevronLeft, ChevronRight } from 'lucide-react';
import { FC, useState, useCallback, useMemo } from 'react';

import FilterBar from '../components/FilterBar';
import TransactionTable, { TxSortField, SortDirection } from '../components/TransactionTable';
import { useTransactions } from '../hooks/useTransactions';
import { AuditFilters } from '../types';

const Transactions: FC = () => {
  const [filters, setFilters] = useState<AuditFilters>({
    limit: 10,
    offset: 0,
  });

  const [sortField, setSortField] = useState<TxSortField>('created_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const { data, isLoading, error } = useTransactions(filters);

  const handleSort = useCallback(
    (field: TxSortField) => {
      if (field === sortField) {
        setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDirection('asc');
      }
    },
    [sortField]
  );

  const sortedItems = useMemo(() => {
    const items = data?.items ?? [];
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
  }, [data, sortField, sortDirection]);

  const totalPages = data ? Math.ceil(data.total / (filters.limit || 10)) : 0;
  const currentPage = data ? Math.floor((filters.offset || 0) / (filters.limit || 10)) + 1 : 1;

  const handlePageChange = (page: number) => {
    setFilters((prev) => ({
      ...prev,
      offset: (page - 1) * (prev.limit || 10),
    }));
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Transactions</h1>
        <p className="mt-1 text-sm text-gray-500">Review and analyze transaction decisions</p>
      </div>

      <FilterBar filters={filters} onFilterChange={setFilters} />

      {isLoading && (
        <div className="flex h-32 items-center justify-center">
          <div className="text-gray-500">Loading transactions...</div>
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          Failed to load transactions. Please try again.
        </div>
      )}

      {!isLoading && !error && (
        <>
          <TransactionTable
            transactions={sortedItems}
            onSort={handleSort}
            sortField={sortField}
            sortDirection={sortDirection}
          />

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-500">
                Showing {(filters.offset || 0) + 1} to{' '}
                {Math.min((filters.offset || 0) + (filters.limit || 10), data?.total || 0)} of{' '}
                {data?.total} results
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage <= 1}
                  className="flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </button>
                <span className="text-sm text-gray-500">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage >= totalPages}
                  className="flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Transactions;
