import React from 'react';
import type { RunStatus } from '../../api/types';

interface BadgeProps {
  status?: RunStatus | string;
  children?: React.ReactNode;
  className?: string;
}

export function Badge({ status, children, className = '' }: BadgeProps) {
  const text = children || status;

  let colorClasses = 'bg-slate-800 text-slate-300 border-slate-700';

  switch (status) {
    case 'RUNNING':
      colorClasses = 'bg-blue-950/80 text-blue-300 border-blue-800/60 animate-pulse';
      break;
    case 'AWAITING_REVIEW':
      colorClasses = 'bg-amber-950/80 text-amber-300 border-amber-800/60';
      break;
    case 'COMPLETED':
      colorClasses = 'bg-emerald-950/80 text-emerald-300 border-emerald-800/60';
      break;
    case 'FAILED':
      colorClasses = 'bg-rose-950/80 text-rose-300 border-rose-800/60';
      break;
    case 'ABORTED':
      colorClasses = 'bg-slate-800 text-slate-400 border-slate-700';
      break;
    case 'QUEUED':
      colorClasses = 'bg-purple-950/80 text-purple-300 border-purple-800/60';
      break;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border ${colorClasses} ${className}`}
    >
      {text}
    </span>
  );
}
