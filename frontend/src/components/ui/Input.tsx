import { cn } from '../../lib/cn';
import type { InputHTMLAttributes } from 'react';

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Input({ label, error, hint, className, id, name, ...props }: Props) {
  const inputId = id ?? label?.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  const inputName = name ?? inputId;

  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label htmlFor={inputId} className="field-label">
          {label}
        </label>
      )}
      <input
        id={inputId}
        name={inputName}
        {...props}
        className={cn(
          'glass-field text-sm',
          error &&
            'border-[var(--color-error-border)] focus:border-[var(--color-error-fg)] focus:shadow-[0_0_0_1px_var(--color-error-border),0_0_0_6px_var(--color-error-bg)]',
          className,
        )}
      />
      {error && <p className="text-xs text-[var(--color-error-fg)]">{error}</p>}
      {hint && !error && <p className="field-hint">{hint}</p>}
    </div>
  );
}
