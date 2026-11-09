import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export function useQuota() {
  const query = useQuery({
    queryKey: ['quota'],
    queryFn: () => api.getQuota(false),
    staleTime: 45_000,
    refetchInterval: 60_000,
  });

  const forceRefresh = async () => {
    return api.getQuota(true);
  };

  return {
    quota: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    forceRefresh,
  };
}
