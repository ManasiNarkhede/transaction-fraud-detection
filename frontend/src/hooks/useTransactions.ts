import { useQuery } from '@tanstack/react-query';

import { transactionsApi } from '../api/transactions';
import { AuditFilters } from '../types';

export const useTransactions = (filters: AuditFilters) => {
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => transactionsApi.list(filters),
  });
};
