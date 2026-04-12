import { cn } from '../../lib/cn';
import type { HTMLAttributes, ReactNode } from 'react';

interface Props extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  glow?: boolean;
}

export function Card({ className, children, glow = false, ...props }: Props) {
  return (
    <div
      {...props}
      className={cn(
        'glass-panel rounded-[1.65rem] p-5 sm:p-6',
        'transition-[transform,border-color,box-shadow] duration-200',
        glow && 'hover:border-[var(--color-info-border)] hover:bg-[rgba(33,40,58,0.72)]',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,var(--color-surface-overlay-strong),transparent)]" />
      {children}
    </div>
  );
}
