import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { decisionsApi } from '../api/decisions';
import { DecisionOverrideRequest } from '../types';

export const useDecisionRecord = (transactionId: string | undefined) => {
  return useQuery({
    queryKey: ['decisionRecord', transactionId],
    queryFn: () => decisionsApi.getByTransaction(transactionId as string),
    enabled: !!transactionId,
  });
};

export const useDecisionOverride = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      transactionId,
      payload,
    }: {
      transactionId: string;
      payload: DecisionOverrideRequest;
    }) => decisionsApi.override(transactionId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['decisionRecord', variables.transactionId] });
      queryClient.invalidateQueries({ queryKey: ['auditRecord', variables.transactionId] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
};
