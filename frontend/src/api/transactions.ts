import {
  TransactionSubmitRequest,
  TransactionDecisionResponse,
  TransactionListResponse,
  AuditFilters,
} from '../types';

import { apiClient } from './client';

export const transactionsApi = {
  list: async (filters: AuditFilters = {}): Promise<TransactionListResponse> => {
    const response = await apiClient.get<TransactionListResponse>('/transactions', {
      params: filters,
    });
    return response.data;
  },

  /** Submit a live transaction for fraud scoring. Returns a decision immediately. */
  submit: async (payload: TransactionSubmitRequest): Promise<TransactionDecisionResponse> => {
    const response = await apiClient.post<TransactionDecisionResponse>(
      '/transactions',
      payload
    );
    return response.data;
  },
};
