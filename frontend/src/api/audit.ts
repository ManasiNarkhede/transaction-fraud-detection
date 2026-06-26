import { AuditFilters, AuditRecord, IntegrityResult, PaginatedResponse } from '../types';

import { apiClient } from './client';

export const auditApi = {
  list: async (filters: AuditFilters): Promise<PaginatedResponse<AuditRecord>> => {
    const response = await apiClient.get<PaginatedResponse<AuditRecord>>('/audit', {
      params: filters,
    });
    return response.data;
  },

  getByTransaction: async (transactionId: string): Promise<AuditRecord> => {
    const response = await apiClient.get<AuditRecord>(`/audit/${transactionId}`);
    return response.data;
  },

  verifyIntegrity: async (): Promise<IntegrityResult> => {
    const response = await apiClient.get<IntegrityResult>('/audit/integrity');
    return response.data;
  },
};
