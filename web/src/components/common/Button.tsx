import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  let variantStyles = 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm';

  switch (variant) {
    case 'secondary':
      variantStyles = 'bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700';
      break;
    case 'danger':
      variantStyles = 'bg-rose-600 hover:bg-rose-500 text-white shadow-sm';
      break;
    case 'outline':
      variantStyles = 'bg-transparent border border-slate-700 hover:bg-slate-800/80 text-slate-200';
      break;
    case 'ghost':
      variantStyles = 'bg-transparent hover:bg-slate-800/60 text-slate-300';
      break;
  }

  let sizeStyles = 'min-h-[44px] px-4 py-2 text-sm';
  if (size === 'sm') sizeStyles = 'min-h-[36px] px-3 py-1.5 text-xs';
  if (size === 'lg') sizeStyles = 'min-h-[52px] px-6 py-3 text-base';

  return (
    <button
      disabled={disabled || isLoading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none ${sizeStyles} ${variantStyles} ${className}`}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        icon && <span className="shrink-0">{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
}
