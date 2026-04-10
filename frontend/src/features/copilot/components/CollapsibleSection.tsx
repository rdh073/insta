import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

export function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)]">
      <button
        type="button"
        onClick={() => setOpen((c) => !c)}
        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-left text-xs font-medium text-[#9aa7cf] transition-colors hover:text-[#dce6ff]"
      >
        <span className="font-mono">{title}</span>
        {open
          ? <ChevronDown className="h-3.5 w-3.5 text-[#7dcfff]" />
          : <ChevronRight className="h-3.5 w-3.5 text-[#4a5578]" />}
      </button>
      {open && (
        <div className="border-t border-[rgba(162,179,229,0.08)] px-3 py-3">
          {children}
        </div>
      )}
    </div>
  );
}
