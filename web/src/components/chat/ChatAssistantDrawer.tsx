import { useState, useRef, useEffect } from 'react';
import {
  X,
  Send,
  Sparkles,
  StopCircle,
  Play,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import { useChatSession } from '../../hooks/useChatSession';
import { Button } from '../common/Button';
import { createPortal } from 'react-dom';

interface ChatAssistantDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  projectId?: string;
  projectName?: string;
  onRunLaunched: (runId: string) => void;
}

export function ChatAssistantDrawer({
  isOpen,
  onClose,
  projectId,
  projectName,
  onRunLaunched,
}: ChatAssistantDrawerProps) {
  const {
    session,
    messages,
    draftIssue,
    setDraftIssue,
    isStreaming,
    isStarting,
    isTerminating,
    isCreatingAndRunning,
    activeTool,
    error,
    startSession,
    sendMessage,
    terminateSession,
    createAndRun,
    resetSession,
  } = useChatSession(projectId);

  const [inputPrompt, setInputPrompt] = useState('');
  const [initialConcept, setInitialConcept] = useState('');
  const [autoApprove, setAutoApprove] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeTool, isStreaming]);

  if (!isOpen) return null;

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!initialConcept.trim() || isStarting) return;
    try {
      await startSession(initialConcept.trim());
      setInitialConcept('');
    } catch {
      // Error handled by hook
    }
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputPrompt.trim() || isStreaming || !session || session.status !== 'ACTIVE') return;
    sendMessage(inputPrompt.trim());
    setInputPrompt('');
  };

  const handleTerminate = async () => {
    if (confirm('Are you sure you want to terminate this exploration session? All scratch containers and worktrees will be removed immediately.')) {
      await terminateSession();
    }
  };

  const handleCreateAndRun = async () => {
    if (!draftIssue || !draftIssue.title.trim() || !draftIssue.body.trim()) return;
    try {
      const res = await createAndRun(draftIssue.title.trim(), draftIssue.body.trim(), autoApprove);
      onClose();
      resetSession();
      onRunLaunched(res.run_id);
    } catch {
      // Error handled by hook
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex flex-col bg-slate-950/95 backdrop-blur-md text-slate-100">
      {/* Top Navigation Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/90 shadow-sm shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-slate-100 truncate flex items-center gap-1.5">
              <span>AI Issue Formulation</span>
              {session && (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-normal bg-indigo-950 text-indigo-300 border border-indigo-800/60 truncate max-w-[120px]">
                  {session.session_slug}
                </span>
              )}
            </h2>
            <p className="text-[11px] text-slate-400 truncate">
              {projectName ? `Project: ${projectName}` : 'Codebase Exploration'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {session && session.status === 'ACTIVE' && (
            <button
              onClick={handleTerminate}
              disabled={isTerminating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50"
              title="Terminate session immediately"
            >
              <StopCircle className="w-3.5 h-3.5 text-white" />
              <span className="hidden sm:inline">Terminate</span>
            </button>
          )}

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 hidden sm:inline-flex"
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Main Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 max-w-3xl mx-auto w-full">
        {/* State 1: No Session Started */}
        {!session && (
          <div className="max-w-lg mx-auto py-8 text-center space-y-6">
            <div className="w-16 h-16 rounded-3xl bg-indigo-600/15 border border-indigo-500/30 flex items-center justify-center mx-auto shadow-inner">
              <Sparkles className="w-8 h-8 text-indigo-400" />
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-100">Collaborative Issue Formulation</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Chat with an Antigravity AI analyst to investigate bugs, explore repository code with real tools,
                clarify edge cases, and formulate a crisp, ready-to-run GitHub issue.
              </p>
            </div>

            <form onSubmit={handleStart} className="space-y-3 text-left">
              <label className="block text-xs font-semibold text-slate-300">
                What concept, bug, or feature would you like to investigate?
              </label>
              <textarea
                value={initialConcept}
                onChange={(e) => setInitialConcept(e.target.value)}
                placeholder="e.g. Explore why notifications fire on server restart or verify Flyway migrations..."
                rows={4}
                className="w-full px-3.5 py-2.5 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
              />

              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isStarting}
                disabled={!initialConcept.trim() || isStarting}
                icon={<Sparkles className="w-4 h-4" />}
                className="w-full justify-center py-2.5"
              >
                Start Exploration Session
              </Button>
            </form>
          </div>
        )}

        {/* State 2: Session Active or Finished */}
        {session && (
          <>
            {/* Status notification banner */}
            {session.status === 'TERMINATED' && (
              <div className="p-3 rounded-2xl bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-center gap-2">
                <StopCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>Exploration session was terminated. Scratch container and worktree were cleaned up.</span>
              </div>
            )}

            {/* Error banner */}
            {error && (
              <div className="p-3 rounded-2xl bg-amber-950/40 border border-amber-800/60 text-xs text-amber-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Messages Feed */}
            <div className="space-y-3 pb-2">
              {messages.map((m, idx) => {
                const isUser = m.role === 'user';
                return (
                  <div
                    key={idx}
                    className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1`}
                  >
                    <div className="text-[10px] text-slate-500 px-1 font-mono">
                      {isUser ? 'You' : 'Antigravity Analyst'}
                    </div>
                    <div
                      className={`max-w-[88%] sm:max-w-[80%] rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                        isUser
                          ? 'bg-indigo-600 text-white rounded-br-sm'
                          : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-sm shadow-sm'
                      }`}
                    >
                      <div className="whitespace-pre-wrap break-words">{m.content}</div>
                    </div>
                  </div>
                );
              })}

              {/* Active Tool Pill */}
              {activeTool && (
                <div className="flex items-center gap-2 text-xs text-indigo-400 font-mono py-1 px-3 rounded-xl bg-slate-900/60 border border-indigo-900/40 animate-pulse w-fit">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{activeTool}</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Live Draft Issue Card */}
            {draftIssue && (
              <div className="rounded-2xl bg-slate-900 border-2 border-indigo-500/40 p-4 sm:p-5 space-y-4 shadow-lg animate-in fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-indigo-400">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Formulated GitHub Issue Statement</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950 border border-emerald-800 text-emerald-300 font-semibold">
                    Ready to Launch
                  </span>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                      Issue Title
                    </label>
                    <input
                      type="text"
                      value={draftIssue.title}
                      onChange={(e) => setDraftIssue({ ...draftIssue, title: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-bold text-slate-100 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                      Problem & Solution Description
                    </label>
                    <textarea
                      value={draftIssue.body}
                      onChange={(e) => setDraftIssue({ ...draftIssue, body: e.target.value })}
                      rows={6}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 leading-relaxed resize-none"
                    />
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2 border-t border-slate-800">
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoApprove}
                      onChange={(e) => setAutoApprove(e.target.checked)}
                      className="w-4 h-4 rounded text-indigo-600 bg-slate-950 border-slate-700 focus:ring-0"
                    />
                    <span>Auto-approve merge on completion</span>
                  </label>

                  <Button
                    variant="primary"
                    size="md"
                    onClick={handleCreateAndRun}
                    isLoading={isCreatingAndRunning}
                    disabled={isCreatingAndRunning || !draftIssue.title.trim()}
                    icon={<Play className="w-4 h-4 text-white" />}
                    className="w-full sm:w-auto justify-center"
                  >
                    🚀 Create on GitHub & Start Run
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom Message Input Bar */}
      {session && session.status === 'ACTIVE' && (
        <div className="p-3 sm:p-4 border-t border-slate-800 bg-slate-900/90 shrink-0">
          <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex items-center gap-2">
            <input
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              placeholder="Ask the analyst to explore files or refine criteria..."
              disabled={isStreaming}
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputPrompt.trim() || isStreaming}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:pointer-events-none transition"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>
        </div>
      )}
    </div>,
    document.body
  );
}
