import { useEffect, useRef, useState } from 'react';
import {
  Archive,
  ArchiveRestore,
  Bookmark,
  BookmarkMinus,
  Loader,
  MoreVertical,
  Pencil,
  Pin,
  PinOff,
  Trash2,
} from 'lucide-react';
import type { MediaSummary } from '../../types/instagram/media';
import { cn } from '../../lib/cn';
import { useMediaActions } from './useMediaActions';
import { EditCaptionDialog } from './EditCaptionDialog';
import type { MediaAction } from './types';

interface Props {
  accountId: string;
  media: MediaSummary;
  className?: string;
}

interface MenuRow {
  action: MediaAction;
  label: string;
  icon: typeof Pencil;
  onSelect: () => void | Promise<unknown>;
  destructive?: boolean;
  confirm?: string;
}

export function MediaActionsMenu({ accountId, media, className }: Props) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const actions = useMediaActions({ accountId, mediaId: media.mediaId });

  // Close menu on outside click + Escape.
  useEffect(() => {
    if (!open) return;

    const onDocClick = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('mousedown', onDocClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onDocClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const rows: MenuRow[] = [
    {
      action: 'edit',
      label: 'Edit caption',
      icon: Pencil,
      onSelect: () => {
        setOpen(false);
        setEditing(true);
      },
    },
    { action: 'pin', label: 'Pin to grid', icon: Pin, onSelect: () => actions.pin() },
    { action: 'unpin', label: 'Unpin from grid', icon: PinOff, onSelect: () => actions.unpin() },
    { action: 'archive', label: 'Archive', icon: Archive, onSelect: () => actions.archive() },
    {
      action: 'unarchive',
      label: 'Unarchive',
      icon: ArchiveRestore,
      onSelect: () => actions.unarchive(),
    },
    { action: 'save', label: 'Save to collection', icon: Bookmark, onSelect: () => actions.save() },
    {
      action: 'unsave',
      label: 'Remove from collection',
      icon: BookmarkMinus,
      onSelect: () => actions.unsave(),
    },
    {
      action: 'delete',
      label: 'Delete post',
      icon: Trash2,
      destructive: true,
      confirm: 'Permanently delete this post? This cannot be undone.',
      onSelect: () => actions.deleteMedia(),
    },
  ];

  function handleRowClick(row: MenuRow) {
    if (row.confirm && !window.confirm(row.confirm)) return;
    setOpen(false);
    void row.onSelect();
  }

  return (
    <div ref={wrapperRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        title="Media actions"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          'inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(162,179,229,0.16)] bg-[rgba(8,12,20,0.72)] text-[#9aa7cf] backdrop-blur-md transition-colors',
          'hover:border-[rgba(125,207,255,0.32)] hover:text-[#7dcfff]',
          actions.isAnyMutating && 'opacity-80',
        )}
      >
        {actions.isAnyMutating ? (
          <Loader className="h-3.5 w-3.5 animate-spin text-[#7dcfff]" />
        ) : (
          <MoreVertical className="h-3.5 w-3.5" />
        )}
      </button>

      {open && (
        <div
          role="menu"
          onClick={(e) => e.stopPropagation()}
          className="glass-panel absolute right-0 top-9 z-30 w-52 rounded-xl border border-[rgba(162,179,229,0.16)] p-1 text-xs shadow-[0_24px_60px_rgba(4,8,18,0.55)]"
        >
          {rows.map((row) => {
            const busy = actions.isMutating(row.action);
            const Icon = row.icon;
            return (
              <button
                key={row.action}
                type="button"
                role="menuitem"
                disabled={busy || actions.isAnyMutating}
                onClick={() => handleRowClick(row)}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  row.destructive
                    ? 'text-[#f7768e] hover:bg-[rgba(247,118,142,0.10)]'
                    : 'text-[#c0caf5] hover:bg-[rgba(125,207,255,0.10)] hover:text-[#7dcfff]',
                )}
              >
                {busy ? <Loader className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
                <span className="flex-1">{row.label}</span>
              </button>
            );
          })}
        </div>
      )}

      <EditCaptionDialog
        open={editing}
        initialCaption={media.captionText}
        saving={actions.isMutating('edit')}
        onClose={() => setEditing(false)}
        onSave={async (caption) => {
          const receipt = await actions.editCaption(caption);
          if (receipt?.success) setEditing(false);
        }}
      />
    </div>
  );
}
