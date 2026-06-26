import { Alert, AlertFilters, AlertListResponse } from '../types';

import { apiClient } from './client';

export const alertsApi = {
  /** List alerts with optional status/severity filters and pagination. */
  list: async (filters: AlertFilters = {}): Promise<AlertListResponse> => {
    const { status, severity, limit = 50, offset = 0 } = filters;
    const params: Record<string, unknown> = { limit, offset };
    if (status) params.status = status;
    if (severity) params.severity = severity;
    const response = await apiClient.get<AlertListResponse>('/alerts', { params });
    return response.data;
  },

  /** Get a single alert by ID. */
  getById: async (alertId: string): Promise<Alert> => {
    const response = await apiClient.get<Alert>(`/alerts/${alertId}`);
    return response.data;
  },

  /** Acknowledge an open alert — transitions it to 'investigating'. */
  acknowledge: async (alertId: string): Promise<Alert> => {
    const response = await apiClient.post<Alert>(`/alerts/${alertId}/acknowledge`);
    return response.data;
  },

  /** Resolve an alert — sets status to 'resolved'. */
  resolve: async (alertId: string): Promise<Alert> => {
    const response = await apiClient.post<Alert>(`/alerts/${alertId}/resolve`);
    return response.data;
  },
};
