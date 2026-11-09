import { Sparkles } from 'lucide-react';
import { ProjectSelector } from '../launcher/ProjectSelector';
import { QuotaPill } from '../quota/QuotaPill';

export function Header() {
  return (
    <header className="sticky top-0 z-30 w-full bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-4 py-3">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
        {/* Left: Branding & Project */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-bold text-sm tracking-tight text-white hidden sm:inline-block">
              Antigravity
            </span>
          </div>

          <ProjectSelector />
        </div>

        {/* Right: Live Quota Pill */}
        <div className="flex items-center gap-2">
          <QuotaPill />
        </div>
      </div>
    </header>
  );
}
