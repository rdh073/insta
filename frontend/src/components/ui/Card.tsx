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
        glow && 'hover:border-[rgba(125,207,255,0.30)] hover:bg-[rgba(24,31,52,0.66)]',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.10),transparent)]" />
      {children}
    </div>
  );
}
