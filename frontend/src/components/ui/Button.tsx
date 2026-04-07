import { cn } from '../../lib/cn';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: ReactNode;
}

const variants = {
  primary:
    'border border-[#7dcfff]/40 bg-[linear-gradient(135deg,rgba(122,162,247,0.92),rgba(125,207,255,0.92)_48%,rgba(187,154,247,0.88))] text-[#08111f] ' +
    'shadow-[0_18px_36px_rgba(122,162,247,0.28),inset_0_1px_0_rgba(255,255,255,0.32)] ' +
    'hover:brightness-105 hover:shadow-[0_20px_44px_rgba(122,162,247,0.34),inset_0_1px_0_rgba(255,255,255,0.36)] active:brightness-95',
  secondary:
    'border border-[rgba(162,179,229,0.2)] bg-[rgba(255,255,255,0.06)] text-[#e8efff] ' +
    'backdrop-blur-xl hover:border-[rgba(125,207,255,0.34)] hover:bg-[rgba(125,207,255,0.12)]',
  ghost:
    'border border-transparent bg-transparent text-[#95a3cb] hover:border-[rgba(162,179,229,0.16)] hover:bg-[rgba(255,255,255,0.05)] hover:text-[#f3f6ff]',
  danger:
    'border border-[#f7768e]/35 bg-[rgba(247,118,142,0.12)] text-[#ffccd7] ' +
    'hover:border-[#f7768e]/55 hover:bg-[rgba(247,118,142,0.18)]',
};

const sizes = {
  sm: 'min-h-10 px-3.5 py-2 text-sm',
  md: 'min-h-11 px-4 py-2.5 text-sm',
  lg: 'min-h-12 px-6 py-3 text-base',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  className,
  children,
  disabled,
  ...props
}: Props) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-[1.1rem] font-semibold tracking-[0.01em] cursor-pointer select-none',
        'transition-[transform,border-color,box-shadow,background-color,color,filter] duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7dcfff]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1020]',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'active:translate-y-px',
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
