import { useEffect, useRef, useState } from 'react';
import { Terminal, Copy, Check, ArrowDown, Radio } from 'lucide-react';
import { useRunStream } from '../../hooks/useRunStream';

interface TerminalStreamProps {
  runId: string;
  isActive: boolean;
}

export function TerminalStream({ runId, isActive }: TerminalStreamProps) {
  const { events, isConnected, error } = useRunStream(runId, true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  const handleCopy = () => {
    const text = events.map((e) => e.raw).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-[520px] rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden font-mono text-xs shadow-inner">
      {/* Terminal Title Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 text-slate-400">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <span className="font-semibold text-slate-200">Execution Log Stream</span>
          {isActive && (
            <span className="inline-flex items-center gap-1.5 text-[10px] text-blue-400 bg-blue-950/60 border border-blue-800/40 px-2 py-0.5 rounded-full">
              <Radio className="w-2.5 h-2.5 animate-pulse" />
              Live SSE
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded-lg transition text-[11px] flex items-center gap-1 ${
              autoScroll ? 'bg-indigo-950/60 text-indigo-300' : 'text-slate-500 hover:text-slate-300'
            }`}
            title="Toggle Auto-Scroll"
          >
            <ArrowDown className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Auto-scroll</span>
          </button>

          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
            title="Copy logs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Terminal Log Console */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2 select-text leading-relaxed">
        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 text-xs">
            {isConnected ? (
              <span>Listening for live container agent events...</span>
            ) : (
              <span>Waiting for execution output...</span>
            )}
          </div>
        )}

        {events.map((evt) => {
          if (evt.type === 'tool') {
            return (
              <div
                key={evt.id}
                className="p-2.5 rounded-xl bg-amber-950/20 border border-amber-800/30 text-amber-200 text-xs space-y-1"
              >
                <div className="flex items-center justify-between text-[10px] text-amber-400 font-bold uppercase tracking-wider">
                  <span>[TOOL CALL] {evt.toolName}</span>
                  <span className="text-slate-500 font-normal">{evt.timestamp}</span>
                </div>
                <div className="text-slate-200 font-mono break-all text-[11px]">
                  {evt.summary || evt.raw}
                </div>
              </div>
            );
          }

          if (evt.type === 'thought') {
            return (
              <div
                key={evt.id}
                className="p-2.5 rounded-xl bg-indigo-950/20 border border-indigo-800/30 text-indigo-200 text-xs space-y-1"
              >
                <div className="flex items-center justify-between text-[10px] text-indigo-400 font-bold uppercase tracking-wider">
                  <span>[AGENT THOUGHT]</span>
                  <span className="text-slate-500 font-normal">{evt.timestamp}</span>
                </div>
                <div className="text-slate-300 break-words text-[11px] whitespace-pre-wrap">
                  {evt.summary || evt.raw}
                </div>
              </div>
            );
          }

          return (
            <div key={evt.id} className="text-slate-400 text-[11px] font-mono break-all leading-5">
              <span className="text-slate-600 mr-2 select-none">{evt.timestamp}</span>
              <span>{evt.raw}</span>
            </div>
          );
        })}

        {error && (
          <div className="text-rose-400 text-xs bg-rose-950/40 p-2 rounded-lg border border-rose-800/50">
            Stream notice: {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
