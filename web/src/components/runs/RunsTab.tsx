import { useState } from 'react';
import { TerminalStream } from './TerminalStream';
import { RunCard } from './RunCard';
import { useRuns } from '../../hooks/useRuns';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { RefreshCw, Terminal, StopCircle, ArrowLeft, Radio } from 'lucide-react';

interface RunsTabProps {
  selectedRunId: string | null;
  onSelectRunId: (id: string | null) => void;
  onNavigateToReview?: () => void;
}

export function RunsTab({ selectedRunId, onSelectRunId, onNavigateToReview }: RunsTabProps) {
  const [filter, setFilter] = useState<string>('');
  const [mobileView, setMobileView] = useState<'list' | 'terminal'>('list');
  const { runs, isLoading, refetch, isRefetching, abortRun, isAborting } = useRuns(filter || undefined);

  const selectedRun = runs.find((r) => r.id === selectedRunId) || runs[0] || null;
  const activeRunningRun = runs.find((r) => r.status === 'RUNNING' || r.status === 'QUEUED');

  const handleAbort = async (runId: string) => {
    if (confirm('Are you sure you want to immediately abort this active run and terminate its container?')) {
      await abortRun(runId);
    }
  };

  const handleSelectRun = (runId: string) => {
    onSelectRunId(runId);
    setMobileView('terminal');
  };

  const isSelectedActive = selectedRun?.status === 'RUNNING' || selectedRun?.status === 'QUEUED';

  return (
    <div className="space-y-4">
      {/* Mobile Top Segmented Tab Switcher */}
      <div className="flex lg:hidden rounded-2xl bg-slate-900 p-1 border border-slate-800 shadow-sm">
        <button
          onClick={() => setMobileView('list')}
          className={`flex-1 py-2 rounded-xl text-xs font-semibold transition active:scale-[0.98] ${
            mobileView === 'list'
              ? 'bg-indigo-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Runs List ({runs.length})
        </button>
        <button
          onClick={() => setMobileView('terminal')}
          className={`flex-1 py-2 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-1.5 active:scale-[0.98] ${
            mobileView === 'terminal'
              ? 'bg-indigo-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>Live Console</span>
          {activeRunningRun && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
          )}
        </button>
      </div>

      {/* Active Run Banner (Visible on mobile runs list if a run is running) */}
      {mobileView === 'list' && activeRunningRun && (
        <button
          onClick={() => handleSelectRun(activeRunningRun.id)}
          className="w-full lg:hidden flex items-center justify-between p-3.5 rounded-2xl bg-gradient-to-r from-indigo-950/60 to-purple-950/40 border border-indigo-700/60 text-left transition active:scale-[0.99]"
        >
          <div className="flex items-center gap-2.5">
            <Radio className="w-4 h-4 text-emerald-400 animate-pulse shrink-0" />
            <div>
              <div className="text-xs font-bold text-slate-100">
                Active Run in Progress: {activeRunningRun.target_type === 'issue' ? `#${activeRunningRun.target_id}` : activeRunningRun.target_id}
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                {activeRunningRun.container_name || 'container running'}
              </div>
            </div>
          </div>
          <span className="text-xs font-semibold text-indigo-400 shrink-0">
            View Live &rarr;
          </span>
        </button>
      )}

      {/* Filter Tabs & Header (Always visible on desktop, visible on mobile in 'list' view) */}
      <div className={`flex flex-wrap items-center justify-between gap-2.5 ${mobileView === 'terminal' ? 'hidden lg:flex' : 'flex'}`}>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 max-w-full">
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

      {/* Main Runs Layout: Responsive Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Runs List (5 cols on desktop, conditionally hidden on mobile if terminal active) */}
        <div className={`lg:col-span-5 space-y-3 ${mobileView === 'terminal' ? 'hidden lg:block' : 'block'}`}>
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
                onSelect={(run) => handleSelectRun(run.id)}
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

        {/* Right: Live Monitor & Terminal Stream (7 cols on desktop, conditionally hidden on mobile if list active) */}
        <div className={`lg:col-span-7 space-y-3 ${mobileView === 'list' ? 'hidden lg:block' : 'block'}`}>
          {selectedRun ? (
            <div className="space-y-3">
              {/* Back to runs button on mobile */}
              <div className="flex lg:hidden items-center justify-between pb-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setMobileView('list')}
                  icon={<ArrowLeft className="w-4 h-4" />}
                >
                  Back to Runs List
                </Button>
                <Badge status={selectedRun.status} />
              </div>

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
            <div className="h-64 rounded-2xl bg-slate-900/40 border border-slate-800 flex flex-col items-center justify-center text-slate-500 text-xs p-6 text-center">
              <Terminal className="w-8 h-8 mb-2 text-slate-600" />
              <span>Select a run from the list to view live terminal execution.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
