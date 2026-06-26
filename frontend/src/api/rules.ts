import { Rule, RuleCreatePayload, RuleUpdatePayload } from '../types';

import { apiClient } from './client';

export const rulesApi = {
  list: async (): Promise<Rule[]> => {
    const response = await apiClient.get<Rule[]>('/rules', {
      params: { limit: 1000, include_inactive: true },
    });
    return response.data;
  },

  create: async (payload: RuleCreatePayload): Promise<Rule> => {
    const response = await apiClient.post<Rule>('/rules', payload);
    return response.data;
  },

  update: async (id: string, payload: RuleUpdatePayload): Promise<Rule> => {
    const response = await apiClient.put<Rule>(`/rules/${id}`, payload);
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/rules/${id}`);
  },

  activate: async (id: string): Promise<Rule> => {
    const response = await apiClient.post<Rule>(`/rules/${id}/activate`);
    return response.data;
  },

  deactivate: async (id: string): Promise<Rule> => {
    const response = await apiClient.post<Rule>(`/rules/${id}/deactivate`);
    return response.data;
  },
};
