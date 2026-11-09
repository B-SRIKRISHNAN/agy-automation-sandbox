import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { RunCreateRequest, RunReviewRequest } from '../api/types';

export function useRuns(statusFilter?: string) {
  const queryClient = useQueryClient();

  const runsQuery = useQuery({
    queryKey: ['runs', statusFilter],
    queryFn: () => api.getRuns(statusFilter),
    // Poll every 3 seconds while there are active or queued runs
    refetchInterval: (query) => {
      const runs = query.state.data?.runs || [];
      const hasActive = runs.some((r) => r.status === 'RUNNING' || r.status === 'QUEUED');
      return hasActive ? 3000 : 15000;
    },
  });

  const startMutation = useMutation({
    mutationFn: (payload: RunCreateRequest) => api.startRun(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      queryClient.invalidateQueries({ queryKey: ['quota'] });
    },
  });

  const abortMutation = useMutation({
    mutationFn: (runId: string) => api.abortRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ runId, payload }: { runId: string; payload: RunReviewRequest }) =>
      api.submitReview(runId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
  });

  return {
    runs: runsQuery.data?.runs ?? [],
    total: runsQuery.data?.total ?? 0,
    isLoading: runsQuery.isLoading,
    isRefetching: runsQuery.isRefetching,
    error: runsQuery.error,
    refetch: runsQuery.refetch,
    startRun: startMutation.mutateAsync,
    isStarting: startMutation.isPending,
    abortRun: abortMutation.mutateAsync,
    isAborting: abortMutation.isPending,
    submitReview: reviewMutation.mutateAsync,
    isSubmittingReview: reviewMutation.isPending,
  };
}

export function useRunDiff(runId: string | null) {
  return useQuery({
    queryKey: ['run-diff', runId],
    queryFn: () => (runId ? api.getRunDiff(runId) : null),
    enabled: Boolean(runId),
    staleTime: 10_000,
  });
}
