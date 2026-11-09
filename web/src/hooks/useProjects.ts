import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

export function useProjects() {
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
    staleTime: 10_000,
  });

  const selectMutation = useMutation({
    mutationFn: api.selectProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
  });

  const registerMutation = useMutation({
    mutationFn: api.registerProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const activeProject = projectsQuery.data?.projects.find((p) => p.is_active);

  return {
    projects: projectsQuery.data?.projects ?? [],
    activeProject,
    isLoading: projectsQuery.isLoading,
    error: projectsQuery.error,
    selectProject: selectMutation.mutate,
    isSelecting: selectMutation.isPending,
    registerProject: registerMutation.mutate,
    isRegistering: registerMutation.isPending,
  };
}
