import { useState } from 'react';
import { FileCode, GitCommit, Sparkles, CheckCircle2, ChevronRight, Layers } from 'lucide-react';
import type { RunDiffResponse } from '../../api/types';

interface DiffViewerProps {
  diff: RunDiffResponse;
}

export function DiffViewer({ diff }: DiffViewerProps) {
  const [activeTab, setActiveTab] = useState<'summary' | 'diff'>(diff.summary ? 'summary' : 'diff');
  const diffLines = (diff.diff_snippet || '').split('\n');

  return (
    <div className="space-y-4">
      {/* Segmented View Switcher (Mobile First) */}
      <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-xl">
        <button
          onClick={() => setActiveTab('summary')}
          className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition ${
            activeTab === 'summary'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-300" />
          <span>AI Resolution Summary</span>
          {diff.summary && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('diff')}
          className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition ${
            activeTab === 'diff'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCode className="w-3.5 h-3.5 text-indigo-400" />
          <span>Unified Diff {diff.commits.length > 0 && `(${diff.commits.length})`}</span>
        </button>
      </div>

      {/* SUMMARY TAB */}
      {activeTab === 'summary' && (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 sm:p-5 space-y-4 shadow-sm">
          {diff.summary ? (
            <SummaryRenderer markdown={diff.summary} />
          ) : (
            <div className="p-8 text-center text-xs text-slate-400 space-y-2">
              <Sparkles className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="font-semibold text-slate-300">No AI summary generated for this run.</p>
              <p className="text-slate-500">Switch to the Unified Diff tab to review raw code modifications.</p>
            </div>
          )}
        </div>
      )}

      {/* DIFF TAB */}
      {activeTab === 'diff' && (
        <div className="space-y-4">
          {/* Worktree Changes & Commits Card */}
          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
              <span className="font-semibold text-slate-300">Worktree Changes:</span>
              <span className="font-mono text-indigo-400 font-bold break-all">
                {diff.diff_stat || 'No file changes detected'}
              </span>
            </div>

            {/* Commits */}
            {diff.commits.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80">
                <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Generated Commits ({diff.commits.length})
                </div>
                <div className="space-y-1 font-mono text-xs text-slate-300">
                  {diff.commits.map((c, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-slate-950/60 truncate">
                      <GitCommit className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      <span className="truncate">{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Touch-Optimized Unified Diff Box */}
          <div className="rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden font-mono text-xs shadow-inner">
            <div className="px-4 py-2.5 bg-slate-900 border-b border-slate-800 text-slate-300 text-xs font-semibold flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-indigo-400" />
                <span>Unified Git Diff</span>
              </div>
              <span className="text-[10px] text-slate-500 font-normal hidden sm:inline">
                Scroll horizontally on mobile
              </span>
            </div>

            <div className="p-3 sm:p-4 overflow-x-auto touch-pan-x [-webkit-overflow-scrolling:touch] max-h-[480px] leading-5 select-text">
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
      )}
    </div>
  );
}

/** Lightweight, mobile-friendly markdown formatter for AI resolution summaries */
function SummaryRenderer({ markdown }: { markdown: string }) {
  const lines = markdown.split('\n');

  return (
    <div className="space-y-3 text-xs sm:text-sm text-slate-300 leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();

        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }

        // Top level header
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={idx} className="text-base sm:text-lg font-bold text-slate-100 pt-1 pb-1 flex items-center gap-2 border-b border-slate-800">
              <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
              <span>{trimmed.replace(/^#\s+/, '')}</span>
            </h2>
          );
        }

        // Section header
        if (trimmed.startsWith('## ') || trimmed.startsWith('### ')) {
          return (
            <h3 key={idx} className="text-sm sm:text-base font-bold text-indigo-300 pt-2 pb-0.5 flex items-center gap-2">
              <ChevronRight className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span>{trimmed.replace(/^###?\s+/, '')}</span>
            </h3>
          );
        }

        // Sub-header
        if (trimmed.startsWith('#### ')) {
          return (
            <h4 key={idx} className="text-xs sm:text-sm font-semibold text-slate-200 pt-1 text-indigo-200/90 flex items-center gap-1.5">
              <Layers className="w-3 h-3 text-slate-400 shrink-0" />
              <span>{trimmed.replace(/^####\s+/, '')}</span>
            </h4>
          );
        }

        // Horizontal separator
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={idx} className="border-slate-800 my-2" />;
        }

        // Bullet point
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const content = trimmed.replace(/^[-*]\s+/, '');
          const isSuccess = content.toLowerCase().includes('passing') || content.toLowerCase().includes('success');
          return (
            <div key={idx} className="flex items-start gap-2 pl-2 sm:pl-3">
              {isSuccess ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
              ) : (
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
              )}
              <span className="flex-1 break-words">{formatInlineStyles(content)}</span>
            </div>
          );
        }

        // Regular paragraph line
        return (
          <p key={idx} className="break-words">
            {formatInlineStyles(line)}
          </p>
        );
      })}
    </div>
  );
}

/** Formats bold, code, and links simply */
function formatInlineStyles(text: string) {
  // Split on bold (**...**) and inline code (`...`)
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);

  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const boldText = part.slice(2, -2);
      const isTestPass = boldText.toLowerCase().includes('passing') || boldText.toLowerCase().includes('0 failure');
      return (
        <strong
          key={i}
          className={`font-semibold ${
            isTestPass ? 'text-emerald-300 font-bold bg-emerald-950/40 px-1 py-0.5 rounded' : 'text-slate-100'
          }`}
        >
          {boldText}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded bg-slate-950 text-indigo-300 font-mono text-[11px] border border-slate-800"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}
