import { useState } from 'react';
import { HardDrive, Loader2 } from 'lucide-react';
import { useStorage } from '../../hooks/useStorage';
import { StorageDrawer } from './StorageDrawer';

export function StoragePill() {
  const { storage, isLoading } = useStorage();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const orphanedCount = storage?.worktrees_orphaned_count || 0;
  const totalHuman = storage?.worktrees_total_human || '0 B';

  let badgeColor = 'bg-slate-900 text-slate-300 border-slate-800 hover:bg-slate-800/80';
  let dotColor = 'bg-emerald-400';

  if (orphanedCount > 0) {
    badgeColor = 'bg-amber-950/40 text-amber-300 border-amber-800/50 hover:bg-amber-900/50';
    dotColor = 'bg-amber-400';
  }

  return (
    <>
      <button
        onClick={() => setIsDrawerOpen(true)}
        className={`inline-flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1.5 rounded-full text-xs font-semibold border transition active:scale-95 shadow-sm shrink-0 ${badgeColor}`}
        title="Environment Storage & Hygiene (Click to inspect or prune)"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          {orphanedCount > 0 && (
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${dotColor}`} />
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`} />
        </span>

        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <div className="flex items-center gap-1 font-mono">
            <HardDrive className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="sm:hidden">{totalHuman}</span>
            <span className="hidden sm:inline">
              {totalHuman} {orphanedCount > 0 ? `(${orphanedCount} stale)` : ''}
            </span>
          </div>
        )}
      </button>

      <StorageDrawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} />
    </>
  );
}
