import { cn } from '../../lib/cn';
import type { ReactNode } from 'react';

type Variant = 'green' | 'red' | 'yellow' | 'blue' | 'gray';

const styles: Record<Variant, string> = {
  green: 'border border-[#9ece6a]/28 bg-[rgba(158,206,106,0.14)] text-[#c8f19b]',
  red: 'border border-[#f7768e]/28 bg-[rgba(247,118,142,0.14)] text-[#ffc4d0]',
  yellow: 'border border-[#e0af68]/28 bg-[rgba(224,175,104,0.14)] text-[#f6d19e]',
  blue: 'border border-[#7dcfff]/26 bg-[rgba(125,207,255,0.14)] text-[#d2f3ff]',
  gray: 'border border-[rgba(162,179,229,0.16)] bg-[rgba(255,255,255,0.05)] text-[#a8b4d8]',
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
