import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Hash, Loader, TrendingUp } from 'lucide-react';
import { discoveryApi } from '../../api/instagram/discovery';
import { useAccountStore } from '../../store/accounts';
import { cn } from '../../lib/cn';

function fmt(n: number | null | undefined) {
  if (n == null) return null;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/** Extract the hashtag being typed at the current cursor position.
 *  Returns the word after the last `#` before the cursor, or null if < 2 chars. */
function hashtagAtCursor(text: string, cursor: number): string | null {
  const before = text.slice(0, cursor);
  const match = before.match(/#(\w{2,})$/);
  return match ? match[1] : null;
}

/** Replace the hashtag being typed at cursor with the selected suggestion. */
function replaceHashtagAtCursor(text: string, cursor: number, replacement: string): { text: string; cursor: number } {
  const before = text.slice(0, cursor);
  const after = text.slice(cursor);
  const replaced = before.replace(/#\w{1,}$/, `#${replacement}`);
  return { text: replaced + after, cursor: replaced.length };
}

interface HashtagResult {
  id: number;
  name: string;
  mediaCount: number | null;
}

interface HashtagTextareaProps {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  className?: string;
  /** Override account used for the hashtag lookup. Falls back to first active account. */
  accountId?: string;
}

export function HashtagTextarea({
  value,
  onChange,
  rows = 6,
  placeholder,
  className,
  accountId: accountIdProp,
}: HashtagTextareaProps) {
  const accounts = useAccountStore((s) => s.accounts);
  const firstActive = accounts.find((a) => a.status === 'active');
  const accountId = accountIdProp ?? firstActive?.id ?? '';

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [results, setResults] = useState<HashtagResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number; width: number }>({ top: 0, left: 0, width: 0 });

  const showDropdown = !!activeTag && !!accountId;

  // Close dropdown on click outside
  useEffect(() => {
    if (!showDropdown) return;
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setActiveTag(null);
        setResults([]);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showDropdown]);

  // Recalculate fixed dropdown position when it opens or on scroll/resize
  useEffect(() => {
    if (!showDropdown || !textareaRef.current) return;
    function updatePos() {
      if (!textareaRef.current) return;
      const rect = textareaRef.current.getBoundingClientRect();
      setDropdownPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
    updatePos();
    window.addEventListener('scroll', updatePos, true);
    window.addEventListener('resize', updatePos);
    return () => {
      window.removeEventListener('scroll', updatePos, true);
      window.removeEventListener('resize', updatePos);
    };
  }, [showDropdown]);

  // Debounced search with abort on stale query
  useEffect(() => {
    if (!activeTag || !accountId) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setActiveIndex(0);
    const abortCtrl = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const data = await discoveryApi.searchHashtags(accountId, activeTag);
        if (!abortCtrl.signal.aborted) {
          setResults(data.slice(0, 8));
        }
      } catch {
        if (!abortCtrl.signal.aborted) {
          setResults([]);
        }
      } finally {
        if (!abortCtrl.signal.aborted) {
          setLoading(false);
        }
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      abortCtrl.abort();
    };
  }, [activeTag, accountId]);

  function pickSuggestion(name: string) {
    const el = textareaRef.current;
    if (!el) return;
    const cursor = el.selectionStart ?? value.length;
    const { text: nextText, cursor: nextCursor } = replaceHashtagAtCursor(value, cursor, name);
    onChange(nextText);
    setActiveTag(null);
    setResults([]);
    // Restore cursor after React re-render
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(nextCursor, nextCursor);
    });
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
    const cursor = e.target.selectionStart ?? e.target.value.length;
    const tag = hashtagAtCursor(e.target.value, cursor);
    if (tag !== activeTag) {
      setActiveTag(tag);
      setResults([]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (!showDropdown) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      if (results.length > 0) {
        pickSuggestion(results[activeIndex]?.name ?? activeTag!);
      } else {
        setActiveTag(null);
        setResults([]);
      }
    } else if (e.key === 'Escape' || e.key === ' ') {
      setActiveTag(null);
      setResults([]);
    }
  }

  function handleSelect() {
    const el = textareaRef.current;
    if (!el) return;
    const cursor = el.selectionStart ?? value.length;
    const tag = hashtagAtCursor(value, cursor);
    if (tag !== activeTag) {
      setActiveTag(tag);
      setResults([]);
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onClick={handleSelect}
        rows={rows}
        placeholder={placeholder}
        className={cn('glass-textarea w-full', className)}
        aria-label={placeholder}
        aria-autocomplete="list"
        aria-expanded={showDropdown}
      />

      {/* Hashtag suggestion dropdown — rendered via portal so it escapes overflow:hidden on glass-panel ancestors */}
      {showDropdown && createPortal(
        <div
          className="z-[200] overflow-hidden rounded-xl border border-[rgba(125,207,255,0.18)] bg-[rgba(8,11,22,0.97)] shadow-[0_8px_32px_rgba(0,0,0,0.55)] backdrop-blur-xl"
          style={{ position: 'fixed', top: dropdownPos.top, left: dropdownPos.left, width: dropdownPos.width }}
          role="listbox"
        >
          {/* Header */}
          <div className="flex items-center gap-2 border-b border-[rgba(162,179,229,0.08)] px-3 py-2">
            <Hash className="h-3.5 w-3.5 text-[#7dcfff]" />
            <span className="text-[11px] font-semibold uppercase tracking-widest text-[#4a5578]">#{activeTag}</span>
            {loading && <Loader className="ml-auto h-3 w-3 animate-spin text-[#7dcfff]" />}
          </div>

          {/* Results list */}
          {!loading && results.length === 0 && (
            <div className="px-3 py-3 text-[12px] text-[#4a5578]">No results</div>
          )}
          {results.map((ht, i) => {
            const count = fmt(ht.mediaCount);
            return (
              <button
                key={ht.id}
                type="button"
                role="option"
                aria-selected={i === activeIndex}
                onMouseEnter={() => setActiveIndex(i)}
                onMouseDown={(e) => { e.preventDefault(); pickSuggestion(ht.name); }}
                className={cn(
                  'flex w-full cursor-pointer items-center justify-between gap-3 px-3 py-2 text-left transition-colors duration-100',
                  i === activeIndex
                    ? 'bg-[rgba(125,207,255,0.10)]'
                    : 'hover:bg-[rgba(255,255,255,0.04)]',
                )}
              >
                <span className="text-[13px] font-medium text-[#c0caf5]">
                  <span className="text-[#7dcfff]">#</span>{ht.name}
                </span>
                {count && (
                  <span className="flex shrink-0 items-center gap-1 text-[11px] text-[#7aa2f7]">
                    <TrendingUp className="h-3 w-3" />
                    {count}
                  </span>
                )}
              </button>
            );
          })}

          {/* Hint */}
          <div className="border-t border-[rgba(162,179,229,0.06)] px-3 py-1.5">
            <p className="text-[10px] text-[#2e3556]">
              ↑↓ navigasi · Enter/Tab pilih · Esc tutup
            </p>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
