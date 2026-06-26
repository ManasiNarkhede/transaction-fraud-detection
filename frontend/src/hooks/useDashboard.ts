import { useQuery } from '@tanstack/react-query';

import { dashboardApi } from '../api/dashboard';

export const useDashboardMetrics = () => {
  return useQuery({
    queryKey: ['dashboardMetrics'],
    queryFn: () => dashboardApi.getMetrics(),
  });
};
