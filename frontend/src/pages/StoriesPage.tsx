import { useState } from 'react';
import toast from 'react-hot-toast';
import { Camera, CheckSquare, Eye, Loader, Play, Square, Trash2 } from 'lucide-react';
import { storiesApi } from '../api/instagram/stories';
import { identityApi } from '../api/instagram/identity';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { StorySummary } from '../types/instagram/story';
import { Button } from '../components/ui/Button';
import { cn } from '../lib/cn';

function StoryRow({
  story,
  checked,
  onCheck,
  onDelete,
}: {
  story: StorySummary;
  checked: boolean;
  onCheck: () => void;
  onDelete: () => void;
}) {
  const isVideo = story.mediaType === 2;
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.02)] px-4 py-3 transition-colors duration-150 hover:border-[rgba(162,179,229,0.14)]">
      <button type="button" onClick={onCheck} className="cursor-pointer text-[#4a5578] hover:text-[#7dcfff] transition-colors duration-150">
        {checked ? <CheckSquare className="h-4 w-4 text-[#7dcfff]" /> : <Square className="h-4 w-4" />}
      </button>

      {/* Thumbnail */}
      <div className="relative h-14 w-10 shrink-0 overflow-hidden rounded-lg border border-[rgba(162,179,229,0.10)]">
        {story.thumbnailUrl ? (
          <>
            <img src={story.thumbnailUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
            {isVideo && (
              <div className="absolute inset-0 flex items-center justify-center bg-[rgba(0,0,0,0.4)]">
                <Play className="h-3 w-3 text-white" />
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[rgba(255,255,255,0.03)]">
            <Camera className="h-3 w-3 text-[#4a5578]" />
          </div>
        )}
      </div>

      {/* Meta */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('glass-chip !px-1.5 !py-0.5 !text-[9px]', isVideo ? 'text-[#bb9af7]' : 'text-[#7aa2f7]')}>
            {isVideo ? 'Video' : 'Photo'}
          </span>
          {story.ownerUsername && (
            <span className="truncate text-xs text-[#6a7aa0]">@{story.ownerUsername}</span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-3 text-[11px] text-[#4a5578]">
          {story.takenAt && <span>{new Date(story.takenAt).toLocaleString()}</span>}
          {story.viewerCount != null && (
            <span className="flex items-center gap-1">
              <Eye className="h-3 w-3" /> {story.viewerCount}
            </span>
          )}
        </div>
        <p className="mt-0.5 font-mono text-[10px] text-[#374060]">{story.storyId}</p>
      </div>

      {/* Delete */}
      <button
        type="button"
        onClick={onDelete}
        className="cursor-pointer rounded-lg p-1.5 text-[#4a5578] transition-colors duration-150 hover:bg-[rgba(247,118,142,0.10)] hover:text-[#f7768e]"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function StoriesPage() {
  const { accountId, setAccountId } = useAccountPicker();
  const [userId, setUserId] = useState('');
  const [stories, setStories] = useState<StorySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [marking, setMarking] = useState(false);

  async function handleLoad() {
    const raw = userId.trim();
    if (!accountId || !raw) return;
    setLoading(true);
    setSelected(new Set());
    try {
      let numericId: number;
      if (/^\d+$/.test(raw)) {
        numericId = Number(raw);
      } else {
        const profile = await identityApi.getUserByUsername(accountId, raw);
        numericId = profile.pk;
      }
      const result = await storiesApi.listUserStories(accountId, numericId);
      setStories(result.items);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function toggleSelect(pk: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(pk)) next.delete(pk);
      else next.add(pk);
      return next;
    });
  }

  async function handleDelete(story: StorySummary) {
    try {
      await storiesApi.deleteStory(accountId, story.pk);
      setStories((prev) => prev.filter((s) => s.pk !== story.pk));
      toast.success('Story deleted');
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function handleMarkSeen() {
    if (selected.size === 0) return;
    setMarking(true);
    try {
      await storiesApi.markSeen(accountId, [...selected]);
      setSelected(new Set());
      toast.success(`Marked ${selected.size} stories as seen`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setMarking(false);
    }
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
            placeholder="Username or User ID"
            className="glass-field w-44 text-sm"
          />
          <Button size="sm" loading={loading} onClick={() => void handleLoad()}>
            Load
          </Button>
          {stories.length > 0 && (
            <span className="glass-chip text-[#7aa2f7]">{stories.length} stories</span>
          )}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        {stories.length === 0 && !loading && (
          <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
            Enter a username or User ID and click Load
          </div>
        )}
        {loading && (
          <div className="flex h-40 items-center justify-center">
            <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
          </div>
        )}
        <div className="mx-auto max-w-2xl space-y-2">
          {stories.map((s) => (
            <StoryRow
              key={s.pk}
              story={s}
              checked={selected.has(s.pk)}
              onCheck={() => toggleSelect(s.pk)}
              onDelete={() => void handleDelete(s)}
            />
          ))}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="shrink-0 border-t border-[rgba(162,179,229,0.10)] bg-[rgba(6,8,16,0.86)] px-5 py-3 backdrop-blur-xl">
          <div className="mx-auto flex max-w-2xl items-center justify-between gap-4">
            <span className="text-sm text-[#7aa2f7]">{selected.size} selected</span>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                Clear
              </Button>
              <Button size="sm" loading={marking} onClick={() => void handleMarkSeen()}>
                <Eye className="h-3.5 w-3.5 mr-1" /> Mark seen
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
