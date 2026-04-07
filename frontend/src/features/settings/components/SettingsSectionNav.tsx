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
      className="flex gap-1 rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] p-1"
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
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7dcfff]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1020]',
            activeSection === id
              ? 'bg-[rgba(125,207,255,0.10)] text-[#7dcfff]'
              : 'text-[#7f8bb3] hover:bg-[rgba(255,255,255,0.04)] hover:text-[#eef4ff]',
          )}
        >
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
