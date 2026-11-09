import React, { useState } from 'react';
import { Play } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import type { Issue } from '../../api/types';

interface LaunchRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedIssue: Issue | null;
  onConfirmLaunch: (payload: {
    target_type: 'issue' | 'session';
    target_id: string;
    auto_approve: boolean;
    engine: string;
  }) => Promise<void>;
  isStarting: boolean;
}

export function LaunchRunModal({
  isOpen,
  onClose,
  selectedIssue,
  onConfirmLaunch,
  isStarting,
}: LaunchRunModalProps) {
  const [targetType, setTargetType] = useState<'issue' | 'session'>('issue');
  const [targetId, setTargetId] = useState(selectedIssue ? String(selectedIssue.number) : '');
  const [autoApprove, setAutoApprove] = useState(false);
  const [engine, setEngine] = useState('auto');

  // Sync if selectedIssue changes
  React.useEffect(() => {
    if (selectedIssue) {
      setTargetType('issue');
      setTargetId(String(selectedIssue.number));
    }
  }, [selectedIssue]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetId.trim()) return;

    await onConfirmLaunch({
      target_type: targetType,
      target_id: targetId.trim(),
      auto_approve: autoApprove,
      engine,
    });
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Launch Autonomous Agent Run">
      <form onSubmit={handleSubmit} className="space-y-4">
        {selectedIssue && targetType === 'issue' && (
          <div className="rounded-xl bg-indigo-950/30 border border-indigo-800/40 p-3">
            <div className="text-xs font-mono text-indigo-400">Issue #{selectedIssue.number}</div>
            <div className="text-sm font-semibold text-slate-100 line-clamp-1 mt-0.5">
              {selectedIssue.title}
            </div>
          </div>
        )}

        {/* Mode Selector */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Execution Archetype</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setTargetType('issue')}
              className={`px-3 py-2 rounded-xl text-xs font-medium border text-center transition ${
                targetType === 'issue'
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-sm'
                  : 'bg-slate-800/50 border-slate-700 text-slate-300 hover:bg-slate-800'
              }`}
            >
              GitHub Issue
            </button>
            <button
              type="button"
              onClick={() => setTargetType('session')}
              className={`px-3 py-2 rounded-xl text-xs font-medium border text-center transition ${
                targetType === 'session'
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-sm'
                  : 'bg-slate-800/50 border-slate-700 text-slate-300 hover:bg-slate-800'
              }`}
            >
              Local Session
            </button>
          </div>
        </div>

        {/* Target Input */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            {targetType === 'issue' ? 'Issue Number' : 'Session Identifier / Name'}
          </label>
          <input
            type="text"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            placeholder={targetType === 'issue' ? '42' : 'refactor-auth-tokens'}
            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs font-mono focus:outline-none focus:border-indigo-500"
            required
          />
        </div>

        {/* Engine Choice */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Container Engine</label>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value)}
            className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
          >
            <option value="auto">Auto (Podman preferred, Docker fallback)</option>
            <option value="docker">Docker</option>
            <option value="podman">Podman</option>
          </select>
        </div>

        {/* Auto Approve Toggle */}
        <label className="flex items-center gap-3 p-3 rounded-xl bg-slate-800/40 border border-slate-800 cursor-pointer">
          <input
            type="checkbox"
            checked={autoApprove}
            onChange={(e) => setAutoApprove(e.target.checked)}
            className="w-4 h-4 rounded text-indigo-600 bg-slate-900 border-slate-700 focus:ring-0 focus:ring-offset-0"
          />
          <div className="text-xs">
            <span className="font-semibold text-slate-200">Auto-Approve & Merge</span>
            <p className="text-slate-400 mt-0.5">
              Automatically merge git branch on success without human review.
            </p>
          </div>
        </label>

        {/* Submit */}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            size="sm"
            isLoading={isStarting}
            icon={<Play className="w-3.5 h-3.5 fill-current" />}
          >
            Start Background Run
          </Button>
        </div>
      </form>
    </Modal>
  );
}
