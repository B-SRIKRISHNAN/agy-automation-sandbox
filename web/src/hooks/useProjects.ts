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
    onSuccess: (newProj) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      // Auto-activate the newly registered project
      if (newProj?.id) {
        selectMutation.mutate(newProj.id);
      }
    },
  });

  const activeProject = projectsQuery.data?.projects.find((p) => p.is_active);

  return {
    projects: projectsQuery.data?.projects ?? [],
    activeProject,
    isLoading: projectsQuery.isLoading,
    error: projectsQuery.error,
    selectProject: selectMutation.mutate,
    selectProjectAsync: selectMutation.mutateAsync,
    isSelecting: selectMutation.isPending,
    selectError: selectMutation.error,
    registerProject: registerMutation.mutate,
    registerProjectAsync: registerMutation.mutateAsync,
    isRegistering: registerMutation.isPending,
    registerError: registerMutation.error,
  };
}
