import { cn } from '../../lib/cn';
import type { ReactNode } from 'react';

type Variant = 'green' | 'red' | 'yellow' | 'blue' | 'gray';

const styles: Record<Variant, string> = {
  green: 'border border-[var(--color-success-border)] bg-[var(--color-success-bg)] text-[var(--color-success-fg)]',
  red: 'border border-[var(--color-error-border)] bg-[var(--color-error-bg)] text-[var(--color-error-fg)]',
  yellow: 'border border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] text-[var(--color-warning-fg)]',
  blue: 'border border-[var(--color-info-border)] bg-[var(--color-info-bg)] text-[var(--color-info-fg)]',
  gray: 'border border-[var(--color-border-subtle)] bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)]',
};

interface Props {
  variant?: Variant;
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Badge({ variant = 'gray', children, className, title }: Props) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex min-h-7 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-[0.01em]',
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
