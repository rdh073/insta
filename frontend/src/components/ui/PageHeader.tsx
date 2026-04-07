import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  icon?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

interface HeaderStatProps {
  label: string;
  value: ReactNode;
  tone?: 'blue' | 'cyan' | 'green' | 'violet' | 'amber' | 'rose';
}

const statTones: Record<NonNullable<HeaderStatProps['tone']>, string> = {
  blue: 'text-[#7aa2f7]',
  cyan: 'text-[#7dcfff]',
  green: 'text-[#9ece6a]',
  violet: 'text-[#bb9af7]',
  amber: 'text-[#e0af68]',
  rose: 'text-[#f7768e]',
};

export function PageHeader({
  eyebrow,
  title,
  description,
  icon,
  actions,
  children,
  className,
}: PageHeaderProps) {
  return (
    <section className={cn('page-header-shell px-5 py-3 sm:px-6', className)}>
      <div className="relative z-10 flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="flex min-w-0 flex-1 items-center gap-2.5">
            {icon && (
              <div className="glass-panel glass-panel-soft flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.9rem] border-[rgba(125,207,255,0.2)]">
                {icon && <span className="scale-75">{icon}</span>}
              </div>
            )}
            <div className="min-w-0">
              {eyebrow && <p className="text-kicker !text-[0.6rem]">{eyebrow}</p>}
              <h1 className={cn('font-semibold text-[#eef4ff] text-base sm:text-lg leading-tight', eyebrow && 'mt-0.5')}>{title}</h1>
              <p className="mt-1 text-sm text-[#8b98bd]">{description}</p>
            </div>
          </div>

          {actions && <div className="flex w-full flex-wrap items-center gap-1.5 xl:w-auto">{actions}</div>}
        </div>

        {children && <div className="relative z-10">{children}</div>}
      </div>
    </section>
  );
}

export function HeaderStat({ label, value, tone = 'blue' }: HeaderStatProps) {
  return (
    <div className="metric-tile">
      <p className="text-kicker !text-[0.58rem] !tracking-[0.14em]">{label}</p>
      <p className={cn('mt-1 text-base font-semibold leading-none', statTones[tone])}>{value}</p>
    </div>
  );
}
