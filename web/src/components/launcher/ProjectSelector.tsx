import { useState } from 'react';
import { FolderGit2, Check, Plus, ChevronDown, GitBranch, Loader2, AlertCircle } from 'lucide-react';
import { useProjects } from '../../hooks/useProjects';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';

export function ProjectSelector() {
  const {
    projects,
    activeProject,
    selectProject,
    registerProject,
    isSelecting,
    selectError,
    isRegistering,
    registerError,
  } = useProjects();

  const [isOpen, setIsOpen] = useState(false);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [newPath, setNewPath] = useState('');
  const [switchingId, setSwitchingId] = useState<string | null>(null);

  const handleSelect = (projId: string) => {
    setSwitchingId(projId);
    selectProject(projId, {
      onSuccess: () => {
        setSwitchingId(null);
        setIsOpen(false);
      },
      onError: () => {
        setSwitchingId(null);
      },
    });
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPath.trim()) return;
    registerProject(newPath.trim(), {
      onSuccess: () => {
        setNewPath('');
        setIsRegisterOpen(false);
        setIsOpen(false);
      },
    });
  };

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-xs font-medium transition active:scale-95 max-w-[140px] sm:max-w-[220px] shrink-0"
        title={activeProject?.path || 'Select Active Project'}
      >
        <FolderGit2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
        <span className="truncate font-medium">{activeProject ? activeProject.name : 'Select Project'}</span>
        <ChevronDown className="w-3 h-3 text-slate-400 shrink-0 ml-0.5" />
      </button>

      {/* Project Switcher Modal / Bottom Sheet */}
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Select Active Project">
        <div className="space-y-3.5">
          {selectError && (
            <div className="rounded-xl bg-rose-950/50 border border-rose-800/60 p-3 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{selectError instanceof Error ? selectError.message : 'Failed to switch project'}</span>
            </div>
          )}

          <div className="space-y-2">
            {projects.map((proj) => {
              const isSelected = proj.is_active;
              const isCurrentSwitching = switchingId === proj.id;

              return (
                <button
                  key={proj.id}
                  onClick={() => handleSelect(proj.id)}
                  disabled={isSelecting}
                  className={`w-full flex items-center justify-between p-3.5 rounded-2xl border text-left transition active:scale-[0.99] ${
                    isSelected
                      ? 'bg-indigo-950/50 border-indigo-500/60 text-indigo-100 shadow-sm'
                      : 'bg-slate-800/40 border-slate-800 hover:bg-slate-800/80 text-slate-300'
                  }`}
                >
                  <div className="truncate pr-3 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm truncate">{proj.name}</span>
                      {isSelected && (
                        <span className="px-1.5 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 text-[10px] font-bold uppercase tracking-wider">
                          Active
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 truncate font-mono mt-0.5">{proj.path}</div>
                    {proj.git_branch && (
                      <div className="flex items-center gap-1 text-[11px] text-slate-500 mt-1">
                        <GitBranch className="w-3 h-3" />
                        <span>{proj.git_branch}</span>
                      </div>
                    )}
                  </div>

                  <div className="shrink-0 flex items-center justify-center w-6 h-6">
                    {isCurrentSwitching ? (
                      <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                    ) : isSelected ? (
                      <div className="w-5 h-5 rounded-full bg-indigo-600 flex items-center justify-center text-white">
                        <Check className="w-3.5 h-3.5" />
                      </div>
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-600 hover:border-slate-400" />
                    )}
                  </div>
                </button>
              );
            })}

            {projects.length === 0 && (
              <p className="text-xs text-slate-400 py-6 text-center">No registered projects found.</p>
            )}
          </div>

          <div className="pt-2 border-t border-slate-800/80">
            <Button
              variant="outline"
              size="md"
              className="w-full justify-center"
              onClick={() => {
                setIsOpen(false);
                setIsRegisterOpen(true);
              }}
              icon={<Plus className="w-4 h-4" />}
            >
              Register Another Repository
            </Button>
          </div>
        </div>
      </Modal>

      {/* Register Path Modal / Bottom Sheet */}
      <Modal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        title="Register Project Repository"
      >
        <form onSubmit={handleRegister} className="space-y-4">
          {registerError && (
            <div className="rounded-xl bg-rose-950/50 border border-rose-800/60 p-3 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{registerError instanceof Error ? registerError.message : 'Failed to register project'}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-200 mb-1.5">
              Absolute Workstation Directory Path
            </label>
            <input
              type="text"
              placeholder="/home/srikrissh777/projects/my-repo"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs font-mono focus:outline-none focus:border-indigo-500"
              autoFocus
            />
            <p className="text-[11px] text-slate-400 mt-1.5">
              Enter the full path to a local Git repository on your machine. Once registered, it will automatically become active.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsRegisterOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" isLoading={isRegistering}>
              Register & Switch
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
