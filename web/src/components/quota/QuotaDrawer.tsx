import { useState } from 'react';
import { RefreshCw, Clock, CheckCircle2, AlertCircle } from 'lucide-react';
import { BottomSheet } from '../common/BottomSheet';
import { Button } from '../common/Button';
import { useQuota } from '../../hooks/useQuota';
import type { QuotaResponse } from '../../api/types';

interface QuotaDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  quota?: QuotaResponse;
  isRefetching?: boolean;
}

export function QuotaDrawer({ isOpen, onClose, quota, isRefetching }: QuotaDrawerProps) {
  const { forceRefresh, refetch } = useQuota();
  const [isManualRefreshing, setIsManualRefreshing] = useState(false);

  const handleManualRefresh = async () => {
    try {
      setIsManualRefreshing(true);
      await forceRefresh();
      await refetch();
    } finally {
      setIsManualRefreshing(false);
    }
  };

  const formatResetTime = (isoString?: string | null) => {
    if (!isoString) return 'Active';
    try {
      const date = new Date(isoString);
      return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title="Antigravity Model Quotas">
      <div className="space-y-6">
        {/* Description Banner */}
        <div className="rounded-xl bg-slate-800/50 border border-slate-700/60 p-3.5 text-xs text-slate-300 leading-relaxed">
          {quota?.description ||
            'Within each group, models share a weekly tier limit and a 5-hour rolling smoothing limit.'}
        </div>

        {/* Quota Groups */}
        <div className="space-y-5">
          {quota?.groups.map((group) => (
            <div
              key={group.name}
              className="rounded-2xl bg-slate-800/40 border border-slate-700/80 p-4 space-y-4"
            >
              <div>
                <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>{group.name}</span>
                </h4>
                {group.description && (
                  <p className="text-xs text-slate-400 mt-0.5">{group.description}</p>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {group.buckets.map((bucket) => {
                  const pct = bucket.remaining_percent;
                  let barColor = 'bg-emerald-500';
                  let textColor = 'text-emerald-400';
                  if (pct < 20) {
                    barColor = 'bg-rose-500';
                    textColor = 'text-rose-400';
                  } else if (pct < 50) {
                    barColor = 'bg-amber-500';
                    textColor = 'text-amber-400';
                  }

                  return (
                    <div
                      key={bucket.id}
                      className="rounded-xl bg-slate-900/80 border border-slate-800 p-3.5 flex flex-col justify-between"
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-xs font-semibold text-slate-200">{bucket.name}</span>
                        <span className={`text-sm font-bold font-mono ${textColor}`}>{pct}%</span>
                      </div>

                      {/* Progress bar */}
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden mb-2.5">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>

                      <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                        <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span>Refreshes: {formatResetTime(bucket.reset_time)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer Meta & Manual Refresh */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            {quota?.cached ? (
              <span className="inline-flex items-center gap-1 text-slate-400">
                <CheckCircle2 className="w-3.5 h-3.5 text-slate-500" />
                Cached (60s TTL)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Live
              </span>
            )}
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={handleManualRefresh}
            isLoading={isManualRefreshing || isRefetching}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Force Refresh
          </Button>
        </div>

        {quota?.error && (
          <div className="rounded-xl bg-rose-950/60 border border-rose-800/60 p-3 text-xs text-rose-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{quota.error}</span>
          </div>
        )}
      </div>
    </BottomSheet>
  );
}
