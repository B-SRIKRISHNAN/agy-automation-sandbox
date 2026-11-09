import { Clock, Box, StopCircle, ArrowRight } from 'lucide-react';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import type { Run } from '../../api/types';

interface RunCardProps {
  run: Run;
  isSelected: boolean;
  onSelect: (run: Run) => void;
  onAbort: (runId: string) => void;
  isAborting?: boolean;
}

export function RunCard({ run, isSelected, onSelect, onAbort, isAborting }: RunCardProps) {
  const isCancellable = run.status === 'RUNNING' || run.status === 'QUEUED' || run.status === 'AWAITING_REVIEW';

  const formatTime = (isoString?: string | null) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div
      onClick={() => onSelect(run)}
      className={`rounded-2xl border p-4 transition cursor-pointer flex flex-col justify-between gap-3 ${
        isSelected
          ? 'bg-slate-900 border-indigo-500/80 shadow-md shadow-indigo-950/40'
          : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
      }`}
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <Badge status={run.status} />
          <span className="text-[11px] font-mono text-slate-500">{formatTime(run.created_at)}</span>
        </div>

        <div className="text-sm font-bold text-slate-100 flex items-center gap-1.5">
          <span>{run.target_type === 'issue' ? `Issue #${run.target_id}` : `Session: ${run.target_id}`}</span>
        </div>

        {run.container_name && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono mt-1.5 truncate">
            <Box className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <span className="truncate">{run.container_name}</span>
          </div>
        )}

        {run.error_message && (
          <p className="text-xs text-rose-400 mt-2 line-clamp-2 bg-rose-950/30 p-2 rounded-lg border border-rose-900/40 font-mono">
            {run.error_message}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 mt-1">
        <div className="flex items-center gap-1 text-xs text-slate-400">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>{run.branch_name || 'main'}</span>
        </div>

        <div className="flex items-center gap-2">
          {isCancellable && (
            <Button
              size="sm"
              variant="danger"
              onClick={(e) => {
                e.stopPropagation();
                onAbort(run.id);
              }}
              isLoading={isAborting}
              icon={<StopCircle className="w-3.5 h-3.5" />}
            >
              Abort
            </Button>
          )}

          <span className="text-slate-400 p-1 hover:text-slate-200">
            <ArrowRight className="w-4 h-4" />
          </span>
        </div>
      </div>
    </div>
  );
}
