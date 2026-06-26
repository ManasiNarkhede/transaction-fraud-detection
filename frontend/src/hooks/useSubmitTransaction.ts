import { useMutation, useQueryClient } from '@tanstack/react-query';

import { transactionsApi } from '../api/transactions';
import { TransactionSubmitRequest } from '../types';

export const useSubmitTransaction = () => {
  const queryClient = useQueryClient();

  const invalidateAfterSubmit = () => {
    queryClient.invalidateQueries({ queryKey: ['dashboardMetrics'] });
    queryClient.invalidateQueries({ queryKey: ['auditLogs'] });
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
    queryClient.invalidateQueries({ queryKey: ['decisions'] });
    queryClient.invalidateQueries({ queryKey: ['alerts'] });
    queryClient.invalidateQueries({ queryKey: ['verifications'] });
  };

  return useMutation({
    mutationFn: (payload: TransactionSubmitRequest) => transactionsApi.submit(payload),
    onSettled: invalidateAfterSubmit,
  });
};
