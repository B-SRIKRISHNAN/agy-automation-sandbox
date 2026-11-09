import { useState } from 'react';
import { TerminalStream } from './TerminalStream';
import { RunCard } from './RunCard';
import { useRuns } from '../../hooks/useRuns';
import { Button } from '../common/Button';
import { RefreshCw, Terminal, StopCircle } from 'lucide-react';

interface RunsTabProps {
  selectedRunId: string | null;
  onSelectRunId: (id: string | null) => void;
  onNavigateToReview?: () => void;
}

export function RunsTab({ selectedRunId, onSelectRunId, onNavigateToReview }: RunsTabProps) {
  const [filter, setFilter] = useState<string>('');
  const { runs, isLoading, refetch, isRefetching, abortRun, isAborting } = useRuns(filter || undefined);

  const selectedRun = runs.find((r) => r.id === selectedRunId) || runs[0] || null;

  const handleAbort = async (runId: string) => {
    if (confirm('Are you sure you want to immediately abort this active run and terminate its container?')) {
      await abortRun(runId);
    }
  };

  const isSelectedActive = selectedRun?.status === 'RUNNING' || selectedRun?.status === 'QUEUED';

  return (
    <div className="space-y-4">
      {/* Filter Tabs & Header */}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {['', 'RUNNING', 'AWAITING_REVIEW', 'COMPLETED', 'FAILED'].map((st) => (
            <button
              key={st}
              onClick={() => setFilter(st)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold tracking-wide transition shrink-0 ${
                filter === st
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {st || 'ALL RUNS'}
            </button>
          ))}
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          isLoading={isRefetching}
          icon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Refresh
        </Button>
      </div>

      {/* Main Runs Layout: Grid on Mobile, Split Pane on Desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Runs List (5 cols on desktop) */}
        <div className="lg:col-span-5 space-y-3">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((n) => (
                <div key={n} className="rounded-2xl bg-slate-900 border border-slate-800 p-4 h-28 animate-pulse" />
              ))}
            </div>
          ) : runs.length > 0 ? (
            runs.map((r) => (
              <RunCard
                key={r.id}
                run={r}
                isSelected={r.id === selectedRun?.id}
                onSelect={(run) => onSelectRunId(run.id)}
                onAbort={handleAbort}
                isAborting={isAborting}
              />
            ))
          ) : (
            <div className="p-8 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
              No runs found matching filter.
            </div>
          )}
        </div>

        {/* Right: Live Monitor & Terminal Stream (7 cols on desktop) */}
        <div className="lg:col-span-7 space-y-3">
          {selectedRun ? (
            <div className="space-y-3">
              {/* Top Banner for Selected Run */}
              <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-100">
                      {selectedRun.target_type === 'issue'
                        ? `Issue #${selectedRun.target_id}`
                        : `Session: ${selectedRun.target_id}`}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">({selectedRun.id})</span>
                  </div>

                  <div className="text-xs text-slate-400 font-mono mt-1">
                    {selectedRun.container_name || 'container allocating...'}
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  {selectedRun.status === 'AWAITING_REVIEW' && onNavigateToReview && (
                    <Button size="sm" variant="primary" onClick={onNavigateToReview}>
                      Review Diff
                    </Button>
                  )}

                  {isSelectedActive && (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => handleAbort(selectedRun.id)}
                      isLoading={isAborting}
                      icon={<StopCircle className="w-3.5 h-3.5" />}
                    >
                      Abort Run
                    </Button>
                  )}
                </div>
              </div>

              {/* Terminal Console */}
              <TerminalStream runId={selectedRun.id} isActive={isSelectedActive} />
            </div>
          ) : (
            <div className="h-64 rounded-2xl bg-slate-900/40 border border-slate-800 flex flex-col items-center justify-center text-slate-500 text-xs">
              <Terminal className="w-8 h-8 mb-2 text-slate-600" />
              <span>Select a run from the list to view live terminal execution.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
