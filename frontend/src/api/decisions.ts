import { Decision, DecisionOverrideRequest, DecisionOverrideResponse } from '../types';

import { apiClient } from './client';

export const decisionsApi = {
  /** Fetch the current decision/status for a transaction by its ID. */
  getByTransaction: async (transactionId: string): Promise<Decision> => {
    const response = await apiClient.get<Decision>(`/decisions/${transactionId}`);
    return response.data;
  },

  /** Override the decision for a transaction (admin only). */
  override: async (
    transactionId: string,
    payload: DecisionOverrideRequest
  ): Promise<DecisionOverrideResponse> => {
    const response = await apiClient.post<DecisionOverrideResponse>(
      `/decisions/${transactionId}/override`,
      payload
    );
    return response.data;
  },
};

