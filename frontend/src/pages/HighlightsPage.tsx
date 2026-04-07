import { useState } from 'react';
import toast from 'react-hot-toast';
import { Bookmark, ChevronDown, ChevronRight, Camera, Loader, Pencil, Trash2 } from 'lucide-react';
import { highlightsApi } from '../api/instagram/highlights';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { HighlightSummary, HighlightDetail } from '../types/instagram/highlight';
import type { StorySummary } from '../types/instagram/story';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';

function StoryThumb({ story }: { story: StorySummary }) {
  return (
    <div className="h-16 w-10 shrink-0 overflow-hidden rounded-lg border border-[rgba(162,179,229,0.10)]">
      {story.thumbnailUrl ? (
        <img src={story.thumbnailUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[rgba(255,255,255,0.03)]">
          <Camera className="h-3 w-3 text-[#4a5578]" />
        </div>
      )}
    </div>
  );
}

function HighlightCard({
  highlight,
  accountId,
  onDeleted,
}: {
  highlight: HighlightSummary;
  accountId: string;
  onDeleted: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<HighlightDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState(highlight.title ?? '');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function toggleExpand() {
    if (!expanded && !detail) {
      setLoading(true);
      try {
        const d = await highlightsApi.getHighlight(accountId, Number(highlight.pk));
        setDetail(d);
      } catch (e) {
        toast.error((e as Error).message);
        return;
      } finally {
        setLoading(false);
      }
    }
    setExpanded((c) => !c);
  }

  async function handleRename() {
    setSaving(true);
    try {
      await highlightsApi.changeTitle(accountId, Number(highlight.pk), newTitle.trim());
      toast.success('Title updated');
      setRenaming(false);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete highlight "${highlight.title}"?`)) return;
    setDeleting(true);
    try {
      await highlightsApi.deleteHighlight(accountId, Number(highlight.pk));
      toast.success('Highlight deleted');
      onDeleted();
    } catch (e) {
      toast.error((e as Error).message);
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-2xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.02)] overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Cover */}
        <div className="h-12 w-8 shrink-0 overflow-hidden rounded-lg border border-[rgba(162,179,229,0.12)]">
          {highlight.cover?.imageUrl ? (
            <img src={highlight.cover.imageUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-[rgba(255,255,255,0.03)]">
              <Bookmark className="h-3 w-3 text-[#4a5578]" />
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-medium text-[#c0caf5]">{highlight.title ?? 'Untitled'}</p>
          <p className="text-[11px] text-[#4a5578]">{highlight.mediaCount ?? 0} stories</p>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setRenaming(true)}
            className="cursor-pointer rounded-lg p-1.5 text-[#4a5578] transition-colors duration-150 hover:bg-[rgba(125,207,255,0.08)] hover:text-[#7dcfff]"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={deleting}
            className="cursor-pointer rounded-lg p-1.5 text-[#4a5578] transition-colors duration-150 hover:bg-[rgba(247,118,142,0.10)] hover:text-[#f7768e] disabled:opacity-40"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => void toggleExpand()}
            className="cursor-pointer rounded-lg p-1.5 text-[#4a5578] transition-colors duration-150 hover:text-[#c0caf5]"
          >
            {loading
              ? <Loader className="h-3.5 w-3.5 animate-spin" />
              : expanded
              ? <ChevronDown className="h-3.5 w-3.5" />
              : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Story thumbnails */}
      {expanded && detail && (
        <div className="border-t border-[rgba(162,179,229,0.08)] px-4 py-3">
          <p className="mb-2 text-[10px] text-[#4a5578]">{detail.items.length} items</p>
          <div className="flex flex-wrap gap-2">
            {detail.items.map((s) => (
              <StoryThumb key={s.pk} story={s} />
            ))}
            {detail.items.length === 0 && (
              <p className="text-xs text-[#374060]">No stories in this highlight</p>
            )}
          </div>
        </div>
      )}

      {/* Rename modal */}
      <Modal open={renaming} onClose={() => setRenaming(false)} title="Rename highlight">
        <div className="space-y-4">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="glass-field w-full"
            placeholder="Highlight title"
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setRenaming(false)}>Cancel</Button>
            <Button size="sm" loading={saving} onClick={() => void handleRename()}>Save</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export function HighlightsPage() {
  const { accountId, setAccountId } = useAccountPicker();
  const [userId, setUserId] = useState('');
  const [highlights, setHighlights] = useState<HighlightSummary[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleLoad() {
    if (!accountId || !userId.trim()) return;
    setLoading(true);
    try {
      const result = await highlightsApi.listUserHighlights(accountId, Number(userId.trim()));
      setHighlights(result.items);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function removeHighlight(pk: string) {
    setHighlights((prev) => prev.filter((h) => h.pk !== pk));
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 border-b border-[rgba(162,179,229,0.08)] px-5 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <AccountPicker value={accountId} onChange={setAccountId} className="w-48" />
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void handleLoad(); }}
            placeholder="User ID (number)"
            className="glass-field w-44 text-sm"
          />
          <Button size="sm" loading={loading} onClick={() => void handleLoad()}>
            Load
          </Button>
          {highlights.length > 0 && (
            <span className="glass-chip text-[#7aa2f7]">{highlights.length} highlights</span>
          )}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        {highlights.length === 0 && !loading && (
          <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
            Enter a User ID and click Load
          </div>
        )}
        {loading && (
          <div className="flex h-40 items-center justify-center">
            <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
          </div>
        )}
        <div className="mx-auto max-w-2xl space-y-2">
          {highlights.map((h) => (
            <HighlightCard
              key={h.pk}
              highlight={h}
              accountId={accountId}
              onDeleted={() => removeHighlight(h.pk)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
