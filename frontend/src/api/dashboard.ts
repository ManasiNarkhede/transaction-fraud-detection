import { DashboardMetrics } from '../types';

import { apiClient } from './client';

export const dashboardApi = {
  getMetrics: async (): Promise<DashboardMetrics> => {
    const response = await apiClient.get<DashboardMetrics>('/dashboard/metrics');
    return response.data;
  },
};
