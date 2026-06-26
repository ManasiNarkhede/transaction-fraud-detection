import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { FC } from 'react';
import { useNavigate } from 'react-router-dom';

import { AuditRecord } from '../types';

export type TxSortField = 'score' | 'created_at';
export type SortDirection = 'asc' | 'desc';

interface TransactionTableProps {
  transactions: AuditRecord[];
  onSort: (field: TxSortField) => void;
  sortField: TxSortField;
  sortDirection: SortDirection;
}

const decisionStyles: Record<string, string> = {
  approve: 'bg-green-100 text-green-800',
  verify: 'bg-yellow-100 text-yellow-800',
  block: 'bg-red-100 text-red-800',
};

const SortIcon: FC<{ field: TxSortField; currentField: TxSortField; direction: SortDirection }> = ({
  field,
  currentField,
  direction,
}) => {
  if (field !== currentField) {
    return <ArrowUpDown className="ml-1 h-4 w-4 text-gray-400" />;
  }
  return direction === 'asc' ? (
    <ArrowUp className="ml-1 h-4 w-4 text-indigo-600" />
  ) : (
    <ArrowDown className="ml-1 h-4 w-4 text-indigo-600" />
  );
};

const formatDate = (timestamp: string) =>
  new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

const TransactionTable: FC<TransactionTableProps> = ({
  transactions,
  onSort,
  sortField,
  sortDirection,
}) => {
  const navigate = useNavigate();

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Transaction ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Decision
              </th>
              <th
                className="cursor-pointer px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-700"
                onClick={() => onSort('score')}
              >
                <div className="flex items-center">
                  Score
                  <SortIcon field="score" currentField={sortField} direction={sortDirection} />
                </div>
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Reason
              </th>
              <th
                className="cursor-pointer px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-700"
                onClick={() => onSort('created_at')}
              >
                <div className="flex items-center">
                  Date
                  <SortIcon field="created_at" currentField={sortField} direction={sortDirection} />
                </div>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {transactions.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-500">
                  No transactions found
                </td>
              </tr>
            ) : (
              transactions.map((tx) => (
                <tr
                  key={tx.id}
                  onClick={() => navigate(`/investigation/${tx.transaction_id}`)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="whitespace-nowrap px-6 py-4 font-mono text-sm font-medium text-indigo-600">
                    {tx.transaction_id}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                        decisionStyles[tx.decision] || 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {tx.decision}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">{tx.score}</td>
                  <td className="max-w-xs truncate px-6 py-4 text-sm text-gray-500" title={tx.reason}>
                    {tx.reason}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {formatDate(tx.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TransactionTable;
