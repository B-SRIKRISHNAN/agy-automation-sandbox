import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

export function useStorage(projectId?: string) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['storage', projectId],
    queryFn: () => api.getStorageInfo(projectId),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const pruneMutation = useMutation({
    mutationFn: (targetProjectId?: string) => api.pruneStorage(targetProjectId || projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['storage'] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
  });

  return {
    storage: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    pruneStorage: pruneMutation.mutateAsync,
    isPruning: pruneMutation.isPending,
    pruneResult: pruneMutation.data,
  };
}
