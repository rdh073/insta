import { Globe, Key, Cpu } from 'lucide-react';
import { cn } from '../../../lib/cn';

export type SettingsSection = 'connection' | 'provider' | 'model';

const sections: { id: SettingsSection; label: string; icon: React.ElementType }[] = [
  { id: 'connection', label: 'Connection', icon: Globe },
  { id: 'provider', label: 'AI Provider', icon: Key },
  { id: 'model', label: 'Runtime Model', icon: Cpu },
];

interface Props {
  activeSection: SettingsSection;
  onNavigate: (section: SettingsSection) => void;
}

export function SettingsSectionNav({ activeSection, onNavigate }: Props) {
  return (
    <nav
      aria-label="Settings sections"
      className="flex gap-1 rounded-[1.2rem] border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay-soft)] p-1"
    >
      {sections.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onNavigate(id)}
          aria-current={activeSection === id ? 'true' : undefined}
          className={cn(
            'flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-[1rem] px-4 py-2.5 text-sm font-medium transition-colors',
            'min-h-[2.75rem]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-canvas)]',
            activeSection === id
              ? 'bg-[var(--color-info-bg)] text-[var(--color-info-fg)]'
              : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-strong)]',
          )}
        >
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
