import { PlayCircle, Terminal, GitPullRequest } from 'lucide-react';
import { useRuns } from '../../hooks/useRuns';

export type TabType = 'launcher' | 'runs' | 'review';

interface BottomNavProps {
  activeTab: TabType;
  onChangeTab: (tab: TabType) => void;
}

export function BottomNav({ activeTab, onChangeTab }: BottomNavProps) {
  const { runs } = useRuns();
  const awaitingCount = runs.filter((r) => r.status === 'AWAITING_REVIEW').length;
  const runningCount = runs.filter((r) => r.status === 'RUNNING' || r.status === 'QUEUED').length;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-slate-950/90 backdrop-blur-lg border-t border-slate-800/80 px-4 py-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]">
      <div className="max-w-md mx-auto grid grid-cols-3 gap-2">
        {/* Launcher Tab */}
        <button
          onClick={() => onChangeTab('launcher')}
          className={`flex flex-col items-center justify-center gap-1 py-1.5 rounded-xl transition ${
            activeTab === 'launcher' ? 'text-indigo-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <PlayCircle className="w-5 h-5" />
          <span className="text-[11px]">Launcher</span>
        </button>

        {/* Runs Tab */}
        <button
          onClick={() => onChangeTab('runs')}
          className={`relative flex flex-col items-center justify-center gap-1 py-1.5 rounded-xl transition ${
            activeTab === 'runs' ? 'text-indigo-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Terminal className="w-5 h-5" />
          <span className="text-[11px]">Runs</span>
          {runningCount > 0 && (
            <span className="absolute top-1 right-[25%] flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
          )}
        </button>

        {/* Review Gate Tab */}
        <button
          onClick={() => onChangeTab('review')}
          className={`relative flex flex-col items-center justify-center gap-1 py-1.5 rounded-xl transition ${
            activeTab === 'review' ? 'text-indigo-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <GitPullRequest className="w-5 h-5" />
          <span className="text-[11px]">Review</span>
          {awaitingCount > 0 && (
            <span className="absolute top-0.5 right-[22%] px-1.5 py-0.2 rounded-full bg-amber-500 text-slate-950 text-[10px] font-bold">
              {awaitingCount}
            </span>
          )}
        </button>
      </div>
    </nav>
  );
}
