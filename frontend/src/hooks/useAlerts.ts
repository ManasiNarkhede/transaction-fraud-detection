import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { alertsApi } from '../api/alerts';
import { AlertFilters } from '../types';

const ALERTS_KEY = ['alerts'];

export const useAlerts = (filters: AlertFilters = {}) => {
  return useQuery({
    queryKey: [...ALERTS_KEY, filters],
    queryFn: () => alertsApi.list(filters),
  });
};

export const useAlert = (alertId: string | undefined) => {
  return useQuery({
    queryKey: [...ALERTS_KEY, alertId],
    queryFn: () => alertsApi.getById(alertId as string),
    enabled: !!alertId,
  });
};

export const useAcknowledgeAlert = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => alertsApi.acknowledge(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ALERTS_KEY });
    },
  });
};

export const useResolveAlert = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => alertsApi.resolve(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ALERTS_KEY });
    },
  });
};
