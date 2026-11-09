import { FileCode, GitCommit } from 'lucide-react';
import type { RunDiffResponse } from '../../api/types';

interface DiffViewerProps {
  diff: RunDiffResponse;
}

export function DiffViewer({ diff }: DiffViewerProps) {
  const diffLines = (diff.diff_snippet || '').split('\n');

  return (
    <div className="space-y-4">
      {/* Diff Stat & Commits Header */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-200">Worktree Changes:</span>
          <span className="font-mono text-indigo-400 font-bold">{diff.diff_stat || 'No file changes'}</span>
        </div>

        {/* Commits */}
        {diff.commits.length > 0 && (
          <div className="space-y-1.5 pt-2 border-t border-slate-800/80">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Generated Commits ({diff.commits.length})
            </div>
            <div className="space-y-1 font-mono text-xs text-slate-300">
              {diff.commits.map((c, i) => (
                <div key={i} className="flex items-center gap-2 p-1.5 rounded-lg bg-slate-950/60 truncate">
                  <GitCommit className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                  <span className="truncate">{c}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Unified Diff Box */}
      <div className="rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden font-mono text-xs shadow-inner">
        <div className="px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-slate-300 text-xs font-semibold flex items-center gap-2">
          <FileCode className="w-4 h-4 text-indigo-400" />
          <span>Unified Git Diff</span>
        </div>

        <div className="p-4 overflow-x-auto max-h-[460px] leading-5 select-text">
          {diffLines.length === 0 || !diff.diff_snippet ? (
            <div className="text-slate-500 py-8 text-center">No diff snippet available for this worktree.</div>
          ) : (
            diffLines.map((line, idx) => {
              let lineStyle = 'text-slate-400';
              let bgStyle = '';

              if (line.startsWith('+') && !line.startsWith('+++')) {
                lineStyle = 'text-emerald-300';
                bgStyle = 'bg-emerald-950/30';
              } else if (line.startsWith('-') && !line.startsWith('---')) {
                lineStyle = 'text-rose-300';
                bgStyle = 'bg-rose-950/30';
              } else if (line.startsWith('@@')) {
                lineStyle = 'text-cyan-400 font-bold';
                bgStyle = 'bg-cyan-950/20';
              } else if (line.startsWith('diff --git')) {
                lineStyle = 'text-amber-300 font-bold mt-2 pt-1 border-t border-slate-800';
              }

              return (
                <div key={idx} className={`px-2 py-0.5 rounded whitespace-pre ${lineStyle} ${bgStyle}`}>
                  {line || ' '}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
