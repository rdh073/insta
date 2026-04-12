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
    'border border-[var(--color-info-border)] bg-[linear-gradient(135deg,var(--color-accent),var(--color-accent-blue)_52%,var(--color-accent-violet))] text-[var(--color-text-strong)] ' +
    'shadow-[0_18px_36px_rgba(0,120,212,0.32),inset_0_1px_0_rgba(255,255,255,0.22)] ' +
    'hover:brightness-105 hover:shadow-[0_20px_44px_rgba(0,120,212,0.38),inset_0_1px_0_rgba(255,255,255,0.28)] active:brightness-95',
  secondary:
    'border border-[var(--color-border-subtle)] bg-[var(--color-surface-overlay)] text-[var(--color-text-primary)] ' +
    'backdrop-blur-xl hover:border-[var(--color-info-border)] hover:bg-[var(--color-info-bg)]',
  ghost:
    'border border-transparent bg-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border-subtle)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-strong)]',
  danger:
    'border border-[var(--color-error-border)] bg-[var(--color-error-bg)] text-[var(--color-error-fg)] ' +
    'hover:border-[var(--color-error-fg)] hover:bg-[rgba(248,81,73,0.2)]',
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
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-canvas)]',
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
