import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/cn';

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: Props) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousActive = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();

    return () => {
      previousActive?.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="absolute inset-0 bg-[rgba(5,8,16,0.76)] backdrop-blur-md" onClick={onClose} />

      <div
        className={cn(
          'glass-panel glass-panel-strong relative z-10 w-full max-w-xl rounded-[2rem]',
          'shadow-[0_34px_90px_rgba(4,8,18,0.62),0_0_0_1px_rgba(125,207,255,0.05)]',
          className,
        )}
      >
        <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.2),transparent)]" />

        <div className="flex items-center justify-between border-b border-[rgba(162,179,229,0.12)] px-5 py-4 sm:px-6">
          <div>
            <p className="text-kicker">Control Surface</p>
            <h2 id="modal-title" className="mt-1 text-base font-semibold text-[#eef4ff]">
              {title}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] text-[#9aa7cf] transition-colors duration-150 hover:border-[rgba(125,207,255,0.28)] hover:text-[#eef4ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7dcfff]/55"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-5 sm:px-6 sm:py-6">{children}</div>
      </div>
    </div>
  );
}
