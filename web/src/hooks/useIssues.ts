import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { IssueCreateRequest } from '../api/types';

export function useIssues() {
  const queryClient = useQueryClient();

  const issuesQuery = useQuery({
    queryKey: ['issues'],
    queryFn: api.getActiveIssues,
    staleTime: 15_000,
    retry: 1,
  });

  const createMutation = useMutation({
    mutationFn: (payload: IssueCreateRequest) => api.createActiveIssue(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    },
  });

  return {
    issues: issuesQuery.data?.issues ?? [],
    total: issuesQuery.data?.total ?? 0,
    isLoading: issuesQuery.isLoading,
    isRefetching: issuesQuery.isRefetching,
    error: issuesQuery.error,
    refetch: issuesQuery.refetch,
    createIssue: createMutation.mutate,
    isCreating: createMutation.isPending,
  };
}
