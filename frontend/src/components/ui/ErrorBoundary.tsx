import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children: ReactNode;
  /** Custom fallback UI. Receives error + reset callback. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  /** Called whenever an error is caught. */
  onError?: (error: Error, info: ErrorInfo) => void;
  /**
   * When any value in this array changes, the boundary resets itself.
   * Useful for resetting on route change.
   */
  resetKeys?: unknown[];
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.props.onError?.(error, info);
    if (import.meta.env.DEV) {
      console.error('[ErrorBoundary] Caught render error:', error, info.componentStack);
    }
  }

  componentDidUpdate(prevProps: Props) {
    const { resetKeys } = this.props;
    if (this.state.error && resetKeys && prevProps.resetKeys) {
      const changed = resetKeys.some((key, i) => key !== prevProps.resetKeys![i]);
      if (changed) this.setState({ error: null });
    }
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback(error, this.reset);
    }

    return <DefaultFallback error={error} reset={this.reset} />;
  }
}

function DefaultFallback({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex h-full min-h-[320px] flex-col items-center justify-center gap-5 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--color-error-border)] bg-[var(--color-error-bg)]">
        <AlertTriangle className="h-7 w-7 text-[var(--color-error-fg)]" />
      </div>

      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-[var(--color-text-strong)]">Something went wrong</p>
        <p className="max-w-sm text-xs text-[var(--color-text-muted)] leading-relaxed">
          {error.message || 'An unexpected render error occurred.'}
        </p>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={reset}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] px-3 py-1.5 text-xs text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-info-border)] hover:text-[var(--color-text-primary)]"
        >
          <RefreshCw className="h-3 w-3" />
          Try again
        </button>
        <a
          href="/"
          className="flex items-center gap-1.5 rounded-lg border border-[var(--color-border-fainter)] bg-[var(--color-surface-overlay-soft)] px-3 py-1.5 text-xs text-[var(--color-text-subtle)] transition-colors hover:text-[var(--color-text-muted)]"
        >
          <Home className="h-3 w-3" />
          Go home
        </a>
      </div>

      {import.meta.env.DEV && (
        <details className="mt-2 w-full max-w-lg text-left">
          <summary className="cursor-pointer text-[11px] text-[var(--color-text-disabled)] hover:text-[var(--color-text-subtle)]">
            Stack trace (dev only)
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded-lg border border-[var(--color-border-fainter)] bg-[rgba(0,0,0,0.4)] p-3 font-mono text-[10px] text-[var(--color-text-subtle)]">
            {error.stack}
          </pre>
        </details>
      )}
    </div>
  );
}
