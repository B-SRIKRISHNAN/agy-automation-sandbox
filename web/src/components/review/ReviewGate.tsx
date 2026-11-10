import { useState } from 'react';
import { GitPullRequest, Check, X, UploadCloud, AlertTriangle } from 'lucide-react';
import { useRuns, useRunDiff } from '../../hooks/useRuns';
import { DiffViewer } from './DiffViewer';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';

interface ReviewGateProps {
  onApprovedOrRejected: () => void;
}

export function ReviewGate({ onApprovedOrRejected }: ReviewGateProps) {
  const { runs, submitReview, isSubmittingReview } = useRuns();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [pushToRemote, setPushToRemote] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resultFeedback, setResultFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Runs in AWAITING_REVIEW state
  const awaitingRuns = runs.filter((r) => r.status === 'AWAITING_REVIEW');
  const activeRunId = selectedRunId || awaitingRuns[0]?.id || runs[0]?.id || null;
  const currentRun = runs.find((r) => r.id === activeRunId);

  const { data: diff, isLoading: isDiffLoading } = useRunDiff(activeRunId);

  const handleDecision = async (approved: boolean) => {
    if (!activeRunId || isSubmitting || isSubmittingReview) return;
    setIsSubmitting(true);
    setResultFeedback(null);
    try {
      const res = await submitReview({
        runId: activeRunId,
        payload: { approved, push: pushToRemote },
      });
      setResultFeedback({
        type: res.status === 'FAILED' ? 'error' : 'success',
        message: res.message,
      });
      onApprovedOrRejected();
    } catch (err) {
      setResultFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Decision submission failed',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!currentRun) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center rounded-3xl bg-slate-900 border border-slate-800">
        <GitPullRequest className="w-10 h-10 text-slate-600 mb-3" />
        <h3 className="text-base font-bold text-slate-200">No Runs Awaiting Review</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm">
          When an automated issue or session run completes agent execution, its git changes will appear here for one-tap approval and merge.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Run Selector if multiple */}
      {runs.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {runs.slice(0, 6).map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedRunId(r.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 transition flex items-center gap-1.5 ${
                r.id === activeRunId
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>{r.target_type === 'issue' ? `#${r.target_id}` : r.target_id}</span>
              <Badge status={r.status} className="text-[10px] py-0 px-1.5" />
            </button>
          ))}
        </div>
      )}

      {/* Review Header Banner */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-slate-100">
              {currentRun.target_type === 'issue'
                ? `Review Fix for Issue #${currentRun.target_id}`
                : `Review Session: ${currentRun.target_id}`}
            </span>
            <Badge status={currentRun.status} />
          </div>
          <div className="text-xs text-slate-400 font-mono mt-1">
            Worktree: {currentRun.worktree_name} · Branch: {currentRun.branch_name} &rarr; {currentRun.base_branch}
          </div>
        </div>

        {currentRun.status === 'AWAITING_REVIEW' && (
          <div className="w-full sm:w-auto flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-3 sm:pt-0 border-t border-slate-800/80 sm:border-0">
            <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer self-start sm:self-auto py-0.5">
              <input
                type="checkbox"
                checked={pushToRemote}
                onChange={(e) => setPushToRemote(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 bg-slate-950 border-slate-700 focus:ring-0"
              />
              <span className="flex items-center gap-1">
                <UploadCloud className="w-3.5 h-3.5 text-indigo-400" />
                Push to remote
              </span>
            </label>

            <div className="grid grid-cols-2 sm:flex items-center gap-2 w-full sm:w-auto">
              <Button
                size="sm"
                variant="danger"
                onClick={() => handleDecision(false)}
                disabled={isSubmitting || isSubmittingReview}
                isLoading={isSubmitting || isSubmittingReview}
                icon={<X className="w-3.5 h-3.5" />}
                className="w-full sm:w-auto justify-center py-2 sm:py-1.5"
              >
                Reject
              </Button>

              <Button
                size="sm"
                variant="primary"
                onClick={() => handleDecision(true)}
                disabled={isSubmitting || isSubmittingReview}
                isLoading={isSubmitting || isSubmittingReview}
                icon={<Check className="w-3.5 h-3.5" />}
                className="w-full sm:w-auto justify-center py-2 sm:py-1.5"
              >
                Approve & Merge
              </Button>
            </div>
          </div>
        )}
      </div>

      {resultFeedback && (
        <div
          className={`rounded-xl border p-3 text-xs flex items-center gap-2 ${
            resultFeedback.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
          }`}
        >
          {resultFeedback.type === 'success' ? (
            <Check className="w-4 h-4 shrink-0 text-emerald-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
          )}
          <span>{resultFeedback.message}</span>
        </div>
      )}

      {/* Diff Content */}
      {isDiffLoading ? (
        <div className="h-48 rounded-2xl bg-slate-900 border border-slate-800 animate-pulse" />
      ) : diff ? (
        <DiffViewer diff={diff} />
      ) : (
        <div className="rounded-2xl bg-slate-900/40 border border-slate-800 p-8 text-center text-xs text-slate-400">
          No git diff available.
        </div>
      )}
    </div>
  );
}
