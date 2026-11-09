import { useState } from 'react';
import { Search, Plus, Play, RefreshCw, AlertCircle, GitPullRequest } from 'lucide-react';
import { useIssues } from '../../hooks/useIssues';
import { useProjects } from '../../hooks/useProjects';
import { useRuns } from '../../hooks/useRuns';
import { IssueCard } from './IssueCard';
import { LaunchRunModal } from './LaunchRunModal';
import { ProjectSelector } from './ProjectSelector';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import type { Issue } from '../../api/types';

interface LauncherTabProps {
  onRunLaunched: (runId: string) => void;
}

export function LauncherTab({ onRunLaunched }: LauncherTabProps) {
  const { activeProject } = useProjects();
  const { issues, isLoading, error, refetch, isRefetching, createIssue, isCreating } = useIssues();
  const { startRun, isStarting } = useRuns();

  const [search, setSearch] = useState('');
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [isLaunchModalOpen, setIsLaunchModalOpen] = useState(false);
  const [isNewIssueModalOpen, setIsNewIssueModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newBody, setNewBody] = useState('');

  const filteredIssues = issues.filter(
    (issue) =>
      issue.title.toLowerCase().includes(search.toLowerCase()) ||
      String(issue.number).includes(search) ||
      issue.labels.some((l) => l.toLowerCase().includes(search.toLowerCase()))
  );

  const handleOpenLaunch = (issue?: Issue) => {
    setSelectedIssue(issue || null);
    setIsLaunchModalOpen(true);
  };

  const handleConfirmLaunch = async (payload: {
    target_type: 'issue' | 'session';
    target_id: string;
    auto_approve: boolean;
    engine: string;
  }) => {
    const run = await startRun({
      project_id: activeProject?.id,
      target_type: payload.target_type,
      target_id: payload.target_id,
      auto_approve: payload.auto_approve,
      engine: payload.engine,
    });
    if (run?.id) {
      onRunLaunched(run.id);
    }
  };

  const handleCreateIssue = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newBody.trim()) return;
    createIssue(
      { title: newTitle.trim(), body: newBody.trim() },
      {
        onSuccess: () => {
          setNewTitle('');
          setNewBody('');
          setIsNewIssueModalOpen(false);
        },
      }
    );
  };

  if (!activeProject) {
    return (
      <div className="flex flex-col items-center justify-center p-10 text-center rounded-3xl bg-slate-900 border border-slate-800">
        <GitPullRequest className="w-12 h-12 text-indigo-400/80 mb-3" />
        <h3 className="text-base font-bold text-slate-100">No Active Project Selected</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm mb-5">
          Select an existing repository or register a new local repository to browse issues and launch automated runs.
        </p>
        <div className="w-full max-w-xs">
          <ProjectSelector />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
          <input
            type="text"
            placeholder="Search issues by title, #number, label..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="px-2.5 sm:px-3"
            onClick={() => refetch()}
            isLoading={isRefetching}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            title="Refresh Issues"
          >
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="flex-1 sm:flex-none justify-center"
            onClick={() => setIsNewIssueModalOpen(true)}
            icon={<Plus className="w-3.5 h-3.5" />}
          >
            New Issue
          </Button>
          <Button
            size="sm"
            variant="primary"
            className="flex-1 sm:flex-none justify-center"
            onClick={() => handleOpenLaunch()}
            icon={<Play className="w-3.5 h-3.5 fill-current" />}
          >
            Custom Run
          </Button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-xl bg-rose-950/40 border border-rose-800/60 p-3.5 text-xs text-rose-300 flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error instanceof Error ? error.message : 'Failed to fetch issues from repository'}</span>
        </div>
      )}

      {/* Issues Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="rounded-2xl bg-slate-900 border border-slate-800 p-4 animate-pulse h-32" />
          ))}
        </div>
      ) : filteredIssues.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredIssues.map((issue) => (
            <IssueCard key={issue.number} issue={issue} onRun={() => handleOpenLaunch(issue)} />
          ))}
        </div>
      ) : (
        <div className="p-10 text-center rounded-2xl bg-slate-900/40 border border-slate-800/60">
          <p className="text-xs text-slate-400">
            {search ? 'No issues matching your search criteria.' : 'No open issues found in active repository.'}
          </p>
        </div>
      )}

      {/* Launch Run Modal */}
      <LaunchRunModal
        isOpen={isLaunchModalOpen}
        onClose={() => setIsLaunchModalOpen(false)}
        selectedIssue={selectedIssue}
        onConfirmLaunch={handleConfirmLaunch}
        isStarting={isStarting}
      />

      {/* New Issue Formulation Modal */}
      <Modal
        isOpen={isNewIssueModalOpen}
        onClose={() => setIsNewIssueModalOpen(false)}
        title="Create New GitHub Issue"
      >
        <form onSubmit={handleCreateIssue} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Issue Title</label>
            <input
              type="text"
              placeholder="e.g. fix(auth): resolve token refresh loop on mobile"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Description / Specification</label>
            <textarea
              rows={4}
              placeholder="Describe the bug or feature request in detail..."
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsNewIssueModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" isLoading={isCreating}>
              Create Issue
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
