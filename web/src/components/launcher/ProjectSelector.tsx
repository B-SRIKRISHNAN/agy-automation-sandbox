import { useState } from 'react';
import { FolderGit2, Check, Plus } from 'lucide-react';
import { useProjects } from '../../hooks/useProjects';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';

export function ProjectSelector() {
  const { projects, activeProject, selectProject, registerProject, isSelecting, isRegistering } =
    useProjects();
  const [isOpen, setIsOpen] = useState(false);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [newPath, setNewPath] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPath.trim()) return;
    registerProject(newPath.trim(), {
      onSuccess: () => {
        setNewPath('');
        setIsRegisterOpen(false);
      },
    });
  };

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-xs font-medium transition active:scale-95 max-w-[200px] truncate"
        title={activeProject?.path || 'Select Active Project'}
      >
        <FolderGit2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
        <span className="truncate">{activeProject ? activeProject.name : 'No Project Active'}</span>
      </button>

      {/* Project Switcher Modal */}
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Select Active Project">
        <div className="space-y-4">
          <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1">
            {projects.map((proj) => (
              <button
                key={proj.id}
                onClick={() => {
                  selectProject(proj.id);
                  setIsOpen(false);
                }}
                disabled={isSelecting}
                className={`w-full flex items-center justify-between p-3 rounded-xl border text-left transition ${
                  proj.is_active
                    ? 'bg-indigo-950/40 border-indigo-700/60 text-indigo-200'
                    : 'bg-slate-800/40 border-slate-800 hover:bg-slate-800 text-slate-300'
                }`}
              >
                <div className="truncate pr-2">
                  <div className="font-semibold text-sm truncate">{proj.name}</div>
                  <div className="text-xs text-slate-400 truncate font-mono mt-0.5">{proj.path}</div>
                </div>
                {proj.is_active && <Check className="w-4 h-4 text-indigo-400 shrink-0" />}
              </button>
            ))}

            {projects.length === 0 && (
              <p className="text-xs text-slate-400 py-4 text-center">No registered projects found.</p>
            )}
          </div>

          <div className="pt-3 border-t border-slate-800">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
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

      {/* Register Path Modal */}
      <Modal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        title="Register Project Repository"
      >
        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Absolute Host Directory Path
            </label>
            <input
              type="text"
              placeholder="/home/user/projects/my-app"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs font-mono focus:outline-none focus:border-indigo-500"
              autoFocus
            />
            <p className="text-[11px] text-slate-400 mt-1.5">
              Enter the full absolute path on your host workstation.
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
              Register Project
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
