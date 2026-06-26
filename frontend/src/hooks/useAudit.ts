import { useQuery } from '@tanstack/react-query';

import { auditApi } from '../api/audit';
import { AuditFilters } from '../types';

export const useAuditLogs = (filters: AuditFilters) => {
  return useQuery({
    queryKey: ['auditLogs', filters],
    queryFn: () => auditApi.list(filters),
  });
};

export const useAuditRecord = (transactionId: string | undefined) => {
  return useQuery({
    queryKey: ['auditRecord', transactionId],
    queryFn: () => auditApi.getByTransaction(transactionId as string),
    enabled: !!transactionId,
  });
};

export const useAuditIntegrity = (enabled: boolean) => {
  return useQuery({
    queryKey: ['auditIntegrity'],
    queryFn: () => auditApi.verifyIntegrity(),
    enabled,
  });
};
