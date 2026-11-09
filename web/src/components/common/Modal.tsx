import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export function Modal({ isOpen, onClose, title, children, maxWidth = 'max-w-md' }: ModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div className="fixed inset-0 z-[100] flex flex-col justify-end sm:justify-center sm:items-center sm:p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal Dialog Content (Bottom-sheet on mobile, centered modal on desktop) */}
      <div
        role="dialog"
        aria-modal="true"
        className={`relative z-10 w-full ${maxWidth} rounded-t-3xl sm:rounded-2xl bg-slate-900 border-t sm:border border-slate-800 p-5 sm:p-6 shadow-2xl flex flex-col max-h-[88dvh] sm:max-h-[85vh] overflow-hidden pb-[calc(1.25rem+env(safe-area-inset-bottom))] sm:pb-6 transition-all animate-in fade-in slide-in-from-bottom-4 duration-200`}
      >
        {/* Mobile drag handle */}
        <div className="mx-auto w-12 h-1.5 bg-slate-700/60 rounded-full mb-3 sm:hidden shrink-0" />

        {/* Header */}
        <div className="flex items-center justify-between pb-3.5 border-b border-slate-800/80 mb-3.5 shrink-0">
          <h3 className="text-base sm:text-lg font-bold text-slate-100">{title}</h3>
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
    </div>,
    document.body
  );
}
