import { useState } from 'react';
import { Zap, Loader2 } from 'lucide-react';
import { useQuota } from '../../hooks/useQuota';
import { QuotaDrawer } from './QuotaDrawer';

export function QuotaPill() {
  const { quota, isLoading, isRefetching } = useQuota();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Find Gemini 5h and weekly buckets
  const geminiGroup = quota?.groups.find((g) => g.name.toLowerCase().includes('gemini'));
  const fiveHBucket = geminiGroup?.buckets.find((b) => b.window === '5h');
  const weeklyBucket = geminiGroup?.buckets.find((b) => b.window === 'weekly');

  const fiveHPercent = fiveHBucket ? fiveHBucket.remaining_percent : 100;
  const weeklyPercent = weeklyBucket ? weeklyBucket.remaining_percent : 100;

  // Determine indicator color based on lowest percentage
  const minPercent = Math.min(fiveHPercent, weeklyPercent);
  let dotColor = 'bg-emerald-400';
  let badgeColor = 'bg-emerald-950/40 text-emerald-300 border-emerald-800/40 hover:bg-emerald-900/50';

  if (minPercent < 20) {
    dotColor = 'bg-rose-400 animate-ping';
    badgeColor = 'bg-rose-950/50 text-rose-300 border-rose-800/50 hover:bg-rose-900/60';
  } else if (minPercent < 50) {
    dotColor = 'bg-amber-400';
    badgeColor = 'bg-amber-950/50 text-amber-300 border-amber-800/50 hover:bg-amber-900/60';
  }

  return (
    <>
      <button
        onClick={() => setIsDrawerOpen(true)}
        className={`inline-flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1.5 rounded-full text-xs font-semibold border transition active:scale-95 shadow-sm shrink-0 ${badgeColor}`}
        title="Antigravity CLI Quota (Click for details)"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${dotColor}`} />
          <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`} />
        </span>

        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <div className="flex items-center gap-1 font-mono">
            <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="sm:hidden">{fiveHPercent}%</span>
            <span className="hidden sm:inline">{fiveHPercent}% (5h) · {weeklyPercent}% (wk)</span>
          </div>
        )}
      </button>

      <QuotaDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        quota={quota}
        isRefetching={isRefetching}
      />
    </>
  );
}
