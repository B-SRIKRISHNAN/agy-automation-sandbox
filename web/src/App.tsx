import { useState } from 'react';
import { Layout } from './components/layout/Layout';
import { type TabType } from './components/layout/BottomNav';
import { LauncherTab } from './components/launcher/LauncherTab';
import { RunsTab } from './components/runs/RunsTab';
import { ReviewGate } from './components/review/ReviewGate';

export function App() {
  const [activeTab, setActiveTab] = useState<TabType>('launcher');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const handleRunLaunched = (runId: string) => {
    setSelectedRunId(runId);
    setActiveTab('runs');
  };

  return (
    <Layout activeTab={activeTab} onChangeTab={setActiveTab}>
      {/* Desktop Tabs Header */}
      <div className="hidden md:flex items-center gap-2 mb-6 border-b border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab('launcher')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold tracking-wide transition ${
            activeTab === 'launcher'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          Issue Launcher
        </button>
        <button
          onClick={() => setActiveTab('runs')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold tracking-wide transition ${
            activeTab === 'runs'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          Active Runs & Terminal
        </button>
        <button
          onClick={() => setActiveTab('review')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold tracking-wide transition ${
            activeTab === 'review'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          Review & Merge Gate
        </button>
      </div>

      {/* Screen Content */}
      {activeTab === 'launcher' && <LauncherTab onRunLaunched={handleRunLaunched} />}

      {activeTab === 'runs' && (
        <RunsTab
          selectedRunId={selectedRunId}
          onSelectRunId={setSelectedRunId}
          onNavigateToReview={() => setActiveTab('review')}
        />
      )}

      {activeTab === 'review' && (
        <ReviewGate onApprovedOrRejected={() => setActiveTab('runs')} />
      )}
    </Layout>
  );
}

export default App;
