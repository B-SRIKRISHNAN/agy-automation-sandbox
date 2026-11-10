import { useState } from 'react';
import { HardDrive, Trash2, RefreshCw, Layers, CheckCircle2 } from 'lucide-react';
import { BottomSheet } from '../common/BottomSheet';
import { Button } from '../common/Button';
import { useStorage } from '../../hooks/useStorage';

interface StorageDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function StorageDrawer({ isOpen, onClose }: StorageDrawerProps) {
  const { storage, isLoading, isRefetching, refetch, pruneStorage, isPruning, pruneResult } = useStorage();
  const [feedback, setFeedback] = useState<string | null>(null);

  const handlePrune = async () => {
    if (!confirm('Safely delete all orphaned worktrees and stopped containers to free disk space?')) {
      return;
    }
    try {
      const res = await pruneStorage(undefined);
      setFeedback(res.message);
      await refetch();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Pruning failed');
    }
  };

  const orphanedItems = storage?.items.filter((item) => item.is_orphaned) || [];
  const activeItems = storage?.items.filter((item) => !item.is_orphaned) || [];

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title="Storage & Environment Hygiene">
      <div className="space-y-5 pb-4">
        {/* Top Summary Cards */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <HardDrive className="w-3.5 h-3.5 text-indigo-400" />
              <span>Worktrees Total</span>
            </div>
            <div className="text-lg font-bold text-slate-100 mt-1">
              {storage?.worktrees_total_human || '0 B'}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {storage?.worktrees_total_count || 0} worktree directories
            </div>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800">
            <div className="flex items-center gap-2 text-xs text-amber-400">
              <Trash2 className="w-3.5 h-3.5" />
              <span>Orphaned Bloat</span>
            </div>
            <div className="text-lg font-bold text-amber-400 mt-1">
              {storage?.worktrees_orphaned_count || 0} stale
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {storage?.containers_count || 0} container(s) detected
            </div>
          </div>
        </div>

        {/* Feedback Banner */}
        {(feedback || pruneResult) && (
          <div className="p-3.5 rounded-2xl bg-emerald-950/60 border border-emerald-700/60 flex items-start gap-2.5 text-xs text-emerald-200">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div className="flex-1 font-medium">
              {feedback || pruneResult?.message}
            </div>
          </div>
        )}

        {/* Action Button */}
        {storage && storage.worktrees_orphaned_count > 0 ? (
          <Button
            variant="danger"
            className="w-full justify-center py-3 text-sm font-semibold rounded-2xl shadow-lg shadow-rose-950/40"
            onClick={handlePrune}
            isLoading={isPruning}
            icon={<Trash2 className="w-4 h-4" />}
          >
            🧹 Prune {storage.worktrees_orphaned_count} Orphaned Worktrees & Free Disk
          </Button>
        ) : (
          <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/50 flex items-center justify-between text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Storage is clean! No orphaned worktrees found.</span>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => refetch()}
              isLoading={isLoading || isRefetching}
              icon={<RefreshCw className="w-3 h-3" />}
            >
              Refresh
            </Button>
          </div>
        )}

        {/* Orphaned Worktrees Breakdown */}
        {orphanedItems.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Orphaned Worktrees ({orphanedItems.length})</span>
              <span className="text-[10px] text-amber-400 font-normal">Ready to purge</span>
            </div>

            <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
              {orphanedItems.map((item) => (
                <div
                  key={item.name}
                  className="p-2.5 rounded-xl bg-slate-900 border border-slate-800/90 flex items-center justify-between text-xs"
                >
                  <div className="truncate pr-2">
                    <div className="font-mono text-slate-200 font-medium truncate">
                      {item.name}
                    </div>
                    {item.branch_name && (
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">
                        branch: {item.branch_name}
                      </div>
                    )}
                  </div>
                  <div className="font-mono text-amber-400 font-semibold shrink-0">
                    {item.size_human}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active Worktrees (Protected) */}
        {activeItems.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Active & Protected ({activeItems.length})</span>
              <span className="text-[10px] text-emerald-400 font-normal">In use</span>
            </div>

            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {activeItems.map((item) => (
                <div
                  key={item.name}
                  className="p-2.5 rounded-xl bg-slate-900 border border-emerald-900/40 flex items-center justify-between text-xs"
                >
                  <div className="truncate pr-2">
                    <div className="font-mono text-slate-200 font-medium truncate flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span>{item.name}</span>
                    </div>
                    {item.run_id && (
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">
                        run: {item.run_id}
                      </div>
                    )}
                  </div>
                  <div className="font-mono text-slate-300 shrink-0">
                    {item.size_human}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Run Session Logs Info */}
        <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>Session Logs (~/.agy-automation)</span>
          </div>
          <span className="font-mono text-slate-200 font-medium">
            {storage?.runs_logs_human || '0 B'}
          </span>
        </div>
      </div>
    </BottomSheet>
  );
}
