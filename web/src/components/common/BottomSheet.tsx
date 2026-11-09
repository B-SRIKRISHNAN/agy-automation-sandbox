import React, { useEffect } from 'react';
import { X } from 'lucide-react';

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function BottomSheet({ isOpen, onClose, title, children }: BottomSheetProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/75 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Slide-Up Panel */}
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-10 w-full max-h-[85vh] rounded-t-3xl bg-slate-900 border-t border-slate-800 p-6 shadow-2xl flex flex-col overflow-hidden pb-[calc(1.5rem+env(safe-area-inset-bottom))]"
      >
        {/* Drag Pill indicator */}
        <div className="mx-auto w-12 h-1.5 bg-slate-700/60 rounded-full mb-4 shrink-0" />

        {/* Title Bar */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4 shrink-0">
          <h3 className="text-lg font-bold text-slate-100">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto overscroll-contain flex-1 pr-1">
          {children}
        </div>
      </div>
    </div>
  );
}
