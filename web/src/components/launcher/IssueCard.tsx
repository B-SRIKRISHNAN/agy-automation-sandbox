import { Play, MessageSquare, Tag, ExternalLink } from 'lucide-react';
import { Button } from '../common/Button';
import type { Issue } from '../../api/types';

interface IssueCardProps {
  issue: Issue;
  onRun: (issue: Issue) => void;
}

export function IssueCard({ issue, onRun }: IssueCardProps) {
  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700/80 p-4 transition flex flex-col justify-between gap-3 shadow-sm">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 text-xs font-mono text-indigo-400">
            <span>#{issue.number}</span>
            <span className="text-slate-600">·</span>
            <span className="text-slate-400 truncate">{issue.author}</span>
          </div>
          {issue.url && (
            <a
              href={issue.url}
              target="_blank"
              rel="noreferrer"
              className="text-slate-500 hover:text-slate-300 p-1"
              title="Open on GitHub"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>

        <h4 className="text-sm font-semibold text-slate-100 mt-1 line-clamp-2 leading-snug">
          {issue.title}
        </h4>

        {issue.body && (
          <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
            {issue.body}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800/60 mt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          {issue.labels.length > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400 truncate bg-slate-800/60 px-2 py-0.5 rounded-md">
              <Tag className="w-3 h-3 text-slate-500 shrink-0" />
              <span className="truncate">{issue.labels[0]}</span>
            </span>
          )}
          {issue.comments_count > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
              <MessageSquare className="w-3 h-3 text-slate-500 shrink-0" />
              <span>{issue.comments_count}</span>
            </span>
          )}
        </div>

        <Button
          size="sm"
          variant="primary"
          onClick={() => onRun(issue)}
          icon={<Play className="w-3.5 h-3.5 fill-current" />}
        >
          Run Fix
        </Button>
      </div>
    </div>
  );
}
