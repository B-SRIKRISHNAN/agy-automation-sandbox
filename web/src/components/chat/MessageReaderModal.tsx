import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Copy, Check, Sparkles, User, ZoomIn, ZoomOut } from 'lucide-react';
import { MarkdownContent } from './MarkdownContent';

interface MessageReaderModalProps {
  isOpen: boolean;
  onClose: () => void;
  role: string;
  content: string;
}

export function MessageReaderModal({
  isOpen,
  onClose,
  role,
  content,
}: MessageReaderModalProps) {
  const [copied, setCopied] = useState(false);
  const [fontSize, setFontSize] = useState<'sm' | 'base' | 'lg'>('base');

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = role === 'user';

  const cycleFontSize = () => {
    if (fontSize === 'sm') setFontSize('base');
    else if (fontSize === 'base') setFontSize('lg');
    else setFontSize('sm');
  };

  return createPortal(
    <div className="fixed inset-0 z-[110] flex flex-col bg-slate-950/95 backdrop-blur-md text-slate-100 animate-in fade-in duration-150">
      {/* Top Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/90 shadow-sm shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
            {isUser ? <User className="w-4 h-4 text-indigo-400" /> : <Sparkles className="w-4 h-4 text-indigo-400" />}
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <span>{isUser ? 'Your Prompt' : 'Analyst Explanation'}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-normal bg-slate-800 text-slate-400 border border-slate-700">
                Reader Mode
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">Distraction-free reading view</p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Font Size Toggle */}
          <button
            onClick={cycleFontSize}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition"
            title={`Current font: ${fontSize}. Tap to cycle size.`}
          >
            {fontSize === 'lg' ? <ZoomOut className="w-3.5 h-3.5" /> : <ZoomIn className="w-3.5 h-3.5" />}
            <span className="uppercase text-[11px] font-mono">{fontSize}</span>
          </button>

          {/* Copy Full Message */}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm transition"
            title="Copy message to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-white" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-white" />
                <span className="hidden sm:inline">Copy</span>
              </>
            )}
          </button>

          {/* Close button */}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition ml-1"
            title="Close reader (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-8 max-w-3xl mx-auto w-full">
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 sm:p-7 shadow-lg">
          <MarkdownContent content={content} fontSize={fontSize} />
        </div>
      </div>

      {/* Footer Quick Dismiss */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-900/80 text-center shrink-0">
        <button
          onClick={onClose}
          className="w-full sm:w-auto px-6 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition"
        >
          Close Reader
        </button>
      </div>
    </div>,
    document.body
  );
}
