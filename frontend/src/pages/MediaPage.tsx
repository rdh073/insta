import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import {
  AtSign,
  Film,
  Heart,
  Image,
  Images,
  Link2,
  Loader,
  MessageCircle,
  Pin,
  PinOff,
  Reply,
  Send,
  Trash2,
  X,
} from 'lucide-react';
import { mediaApi } from '../api/instagram/media';
import { commentsApi } from '../api/instagram/comments';
import { identityApi } from '../api/instagram/identity';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { MediaSummary } from '../types/instagram/media';
import type { CommentPage } from '../types/instagram/comment';
import { Button } from '../components/ui/Button';
import { useMediaStore } from '../store/media';
import { MediaActionsMenu } from '../features/media/MediaActionsMenu';
import { MediaLikersPanel } from '../features/media/MediaLikersPanel';
import { UserClipsGrid } from '../features/media/UserClipsGrid';
import { UserTaggedGrid } from '../features/media/UserTaggedGrid';
import { LikedMediasTab } from '../features/collections/LikedMediasTab';
import { cn } from '../lib/cn';

type DrawerTab = 'detail' | 'comments' | 'likers';
type FeedTab = 'posts' | 'clips' | 'tagged' | 'liked';

const MEDIA_TYPE_LABEL: Record<number, string> = { 1: 'Photo', 2: 'Video', 8: 'Album' };

function mediaTypeIcon(t: number) {
  if (t === 2) return <Film className="h-3 w-3" />;
  if (t === 8) return <Images className="h-3 w-3" />;
  return <Image className="h-3 w-3" />;
}

function MediaCard({
  accountId,
  media,
  selected,
  onClick,
}: {
  accountId: string;
  media: MediaSummary;
  selected: boolean;
  onClick: () => void;
}) {
  const thumb = media.resources[0]?.thumbnailUrl ?? null;
  return (
    <div
      className={cn(
        'group relative aspect-square w-full overflow-hidden rounded-2xl border transition-all duration-200',
        selected
          ? 'border-[rgba(125,207,255,0.40)] ring-1 ring-[rgba(125,207,255,0.24)]'
          : 'border-[rgba(162,179,229,0.10)] hover:border-[rgba(125,207,255,0.24)]',
      )}
    >
      <button type="button" onClick={onClick} className="block h-full w-full cursor-pointer">
        {thumb ? (
          <img src={thumb} alt={media.captionText || 'media'} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[rgba(255,255,255,0.03)]">
            {mediaTypeIcon(media.mediaType)}
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-1 bg-gradient-to-t from-[rgba(4,6,14,0.82)] to-transparent p-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
          <span className="flex items-center gap-1 text-[10px] text-[#9aa7cf]">
            <Heart className="h-2.5 w-2.5 text-[#f7768e]" /> {media.likeCount}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-[#9aa7cf]">
            <MessageCircle className="h-2.5 w-2.5 text-[#7dcfff]" /> {media.commentCount}
          </span>
        </div>
      </button>
      <div className="pointer-events-none absolute left-1.5 top-1.5">
        <span className="glass-chip !px-1.5 !py-0.5 !text-[9px]">
          {mediaTypeIcon(media.mediaType)}
          {MEDIA_TYPE_LABEL[media.mediaType] ?? media.mediaType}
        </span>
      </div>
      {accountId && (
        <div className="absolute right-1.5 top-1.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100">
          <MediaActionsMenu accountId={accountId} media={media} />
        </div>
      )}
    </div>
  );
}

function CommentsPanel({ accountId, mediaId }: { accountId: string; mediaId: string }) {
  const [page, setPage] = useState<CommentPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [newText, setNewText] = useState('');
  const [replyTo, setReplyTo] = useState<{ pk: number; author: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [busy, setBusy] = useState<Record<number, boolean>>({});

  async function load() {
    setLoading(true);
    try {
      const result = await commentsApi.listCommentsPage(accountId, mediaId, 20);
      setPage(result);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    if (!newText.trim()) return;
    setSending(true);
    try {
      await commentsApi.createComment(accountId, mediaId, newText.trim(), replyTo?.pk);
      setNewText('');
      setReplyTo(null);
      await load();
      toast.success(replyTo ? 'Reply posted' : 'Comment posted');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  function setBusyFor(pk: number, val: boolean) {
    setBusy((prev) => ({ ...prev, [pk]: val }));
  }

  async function handleLike(pk: number, hasLiked: boolean | null) {
    setBusyFor(pk, true);
    try {
      if (hasLiked) {
        await commentsApi.unlikeComment(accountId, pk);
      } else {
        await commentsApi.likeComment(accountId, pk);
      }
      setPage((prev) =>
        prev
          ? {
              ...prev,
              comments: prev.comments.map((c) =>
                c.pk === pk
                  ? { ...c, hasLiked: !hasLiked, likeCount: (c.likeCount ?? 0) + (hasLiked ? -1 : 1) }
                  : c,
              ),
            }
          : prev,
      );
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusyFor(pk, false);
    }
  }

  async function handleDelete(pk: number) {
    setBusyFor(pk, true);
    try {
      await commentsApi.deleteComment(accountId, mediaId, pk);
      setPage((prev) =>
        prev
          ? { ...prev, comments: prev.comments.filter((c) => c.pk !== pk), count: prev.count - 1 }
          : prev,
      );
      toast.success('Comment deleted');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusyFor(pk, false);
    }
  }

  async function handlePin(pk: number) {
    setBusyFor(pk, true);
    try {
      const r = await commentsApi.pinComment(accountId, mediaId, pk);
      if (r.success) toast.success('Comment pinned');
      else toast.error(r.reason || 'Pin failed');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusyFor(pk, false);
    }
  }

  async function handleUnpin(pk: number) {
    setBusyFor(pk, true);
    try {
      const r = await commentsApi.unpinComment(accountId, mediaId, pk);
      if (r.success) toast.success('Comment unpinned');
      else toast.error(r.reason || 'Unpin failed');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusyFor(pk, false);
    }
  }

  if (!page && !loading) {
    return (
      <button
        type="button"
        onClick={load}
        className="cursor-pointer text-sm text-[#7dcfff] underline-offset-2 hover:underline"
      >
        Load comments
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {loading && <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />}
      {page && (
        <>
          <p className="text-[11px] text-[#4a5578]">{page.count} comments</p>
          <div className="space-y-2">
            {page.comments.map((c) => (
              <div
                key={c.pk}
                className="group rounded-xl border border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.02)] px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-[#7dcfff]">@{c.author}</p>
                    <p className="mt-0.5 text-xs leading-5 text-[#c0caf5]">{c.text}</p>
                    {c.likeCount != null && c.likeCount > 0 && (
                      <p className="mt-0.5 text-[10px] text-[#4a5578]">
                        <Heart className="mr-0.5 inline h-2.5 w-2.5 text-[#f7768e]" />
                        {c.likeCount}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      disabled={busy[c.pk]}
                      onClick={() => void handleLike(c.pk, c.hasLiked)}
                      title={c.hasLiked ? 'Unlike' : 'Like'}
                      className={cn(
                        'flex h-6 w-6 items-center justify-center rounded-md transition-colors disabled:opacity-40',
                        c.hasLiked
                          ? 'text-[#f7768e] hover:bg-[rgba(247,118,142,0.12)]'
                          : 'text-[#59658c] hover:bg-[rgba(247,118,142,0.12)] hover:text-[#f7768e]',
                      )}
                    >
                      <Heart className={cn('h-3 w-3', c.hasLiked && 'fill-current')} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setReplyTo({ pk: c.pk, author: c.author })}
                      title="Reply"
                      className="flex h-6 w-6 items-center justify-center rounded-md text-[#59658c] transition-colors hover:bg-[rgba(125,207,255,0.12)] hover:text-[#7dcfff]"
                    >
                      <Reply className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      disabled={busy[c.pk]}
                      onClick={() => void handlePin(c.pk)}
                      title="Pin"
                      className="flex h-6 w-6 items-center justify-center rounded-md text-[#59658c] transition-colors hover:bg-[rgba(187,154,247,0.12)] hover:text-[#bb9af7] disabled:opacity-40"
                    >
                      <Pin className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      disabled={busy[c.pk]}
                      onClick={() => void handleUnpin(c.pk)}
                      title="Unpin"
                      className="flex h-6 w-6 items-center justify-center rounded-md text-[#59658c] transition-colors hover:bg-[rgba(187,154,247,0.12)] hover:text-[#bb9af7] disabled:opacity-40"
                    >
                      <PinOff className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      disabled={busy[c.pk]}
                      onClick={() => void handleDelete(c.pk)}
                      title="Delete"
                      className="flex h-6 w-6 items-center justify-center rounded-md text-[#59658c] transition-colors hover:bg-[rgba(247,118,142,0.12)] hover:text-[#f7768e] disabled:opacity-40"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {replyTo && (
            <div className="flex items-center justify-between rounded-lg border border-[rgba(125,207,255,0.16)] bg-[rgba(125,207,255,0.06)] px-3 py-1.5">
              <p className="text-[11px] text-[#7dcfff]">
                Replying to <span className="font-semibold">@{replyTo.author}</span>
              </p>
              <button
                type="button"
                onClick={() => setReplyTo(null)}
                className="text-[#59658c] hover:text-[#7dcfff]"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          <div className="flex gap-2">
            <input
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleSend(); }}
              placeholder={replyTo ? `Reply to @${replyTo.author}…` : 'Add a comment…'}
              className="glass-field flex-1 text-sm"
            />
            <Button size="sm" loading={sending} onClick={() => void handleSend()}>
              <Send className="h-3.5 w-3.5" />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function extractShortcode(input: string): string {
  const match = /instagram\.com\/(?:p|reel|tv)\/([A-Za-z0-9_-]+)/.exec(input);
  return match ? match[1] : input.trim();
}

export function MediaPage() {
  const { accountId, setAccountId } = useAccountPicker();

  const userId     = useMediaStore((s) => s.userId);
  const media      = useMediaStore((s) => s.media);
  const selected   = useMediaStore((s) => s.selected);
  const drawerTab  = useMediaStore((s) => s.drawerTab);
  const feedTab    = useMediaStore((s) => s.feedTab);

  const setScopeAccountId = useMediaStore((s) => s.setScopeAccountId);
  const setUserId    = useMediaStore((s) => s.setUserId);
  const setMedia     = useMediaStore((s) => s.setMedia);
  const prependMedia = useMediaStore((s) => s.prependMedia);
  const setSelected  = useMediaStore((s) => s.setSelected);
  const setDrawerTab = useMediaStore((s) => s.setDrawerTab);
  const setFeedTab   = useMediaStore((s) => s.setFeedTab);

  const [postUrl, setPostUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [urlLoading, setUrlLoading] = useState(false);
  const [resolvedUserId, setResolvedUserId] = useState<number | null>(null);
  const selectedMedia = selected ?? null;

  useEffect(() => {
    setScopeAccountId(accountId);
  }, [accountId, setScopeAccountId]);

  async function handleLoad() {
    const raw = userId.trim();
    if (!accountId || !raw) return;
    setLoading(true);
    try {
      let numericId: number;
      if (/^\d+$/.test(raw)) {
        numericId = Number(raw);
      } else {
        const profile = await identityApi.getUserByUsername(accountId, raw);
        numericId = profile.pk;
      }
      setResolvedUserId(numericId);
      const result = await mediaApi.getUserMedias(accountId, numericId, 24);
      setMedia(result.posts);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGoToPost() {
    const raw = postUrl.trim();
    if (!accountId || !raw) return;
    const code = extractShortcode(raw);
    setUrlLoading(true);
    try {
      const m = await mediaApi.getByCode(accountId, code);
      prependMedia(m);
      setDrawerTab('comments');
      setPostUrl('');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUrlLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 border-b border-[rgba(162,179,229,0.08)] px-5 py-3 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <AccountPicker
            value={accountId}
            onChange={(id) => {
              setScopeAccountId(id);
              setAccountId(id);
            }}
            className="w-48"
          />
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
          {media.length > 0 && (
            <span className="glass-chip text-[#7aa2f7]">{media.length} posts</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 text-[11px] text-[#4a5578]">
            <Link2 className="h-3 w-3" />
            <span>Post URL</span>
          </div>
          <input
            value={postUrl}
            onChange={(e) => setPostUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void handleGoToPost(); }}
            placeholder="https://instagram.com/p/… or shortcode"
            className="glass-field w-72 text-sm"
          />
          <Button size="sm" variant="secondary" loading={urlLoading} onClick={() => void handleGoToPost()}>
            Go to Post
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Grid */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Feed tab switcher */}
          {accountId && (
            <div className="mb-4 flex items-center gap-1 rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.02)] p-1">
              {(['posts', 'clips', 'tagged', 'liked'] as FeedTab[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setFeedTab(t)}
                  className={cn(
                    'flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-medium capitalize transition-colors duration-150',
                    feedTab === t
                      ? 'bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                      : 'text-[#6a7aa0] hover:text-[#c0caf5]',
                  )}
                >
                  {t === 'posts' && <Image className="h-3 w-3" />}
                  {t === 'clips' && <Film className="h-3 w-3" />}
                  {t === 'tagged' && <AtSign className="h-3 w-3" />}
                  {t === 'liked' && <Heart className="h-3 w-3" />}
                  {t}
                </button>
              ))}
            </div>
          )}

          {feedTab === 'posts' && (
            <>
              {media.length === 0 && !loading && (
                <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
                  Enter a username or User ID and click Load
                </div>
              )}
              {loading && (
                <div className="flex h-40 items-center justify-center">
                  <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {media.map((m) => (
                  <MediaCard
                    key={m.pk}
                    accountId={accountId}
                    media={m}
                    selected={selectedMedia?.pk === m.pk}
                    onClick={() => { setSelected(m); setDrawerTab('detail'); }}
                  />
                ))}
              </div>
            </>
          )}

          {feedTab === 'clips' && (
            <UserClipsGrid
              accountId={accountId}
              userId={resolvedUserId}
              selectedPk={selectedMedia?.pk ?? null}
              onSelect={(m) => { setSelected(m); setDrawerTab('detail'); }}
            />
          )}

          {feedTab === 'tagged' && (
            <UserTaggedGrid
              accountId={accountId}
              userId={resolvedUserId}
              selectedPk={selectedMedia?.pk ?? null}
              onSelect={(m) => { setSelected(m); setDrawerTab('detail'); }}
            />
          )}

          {feedTab === 'liked' && (
            <LikedMediasTab
              accountId={accountId}
              selectedPk={selectedMedia?.pk ?? null}
              onSelect={(m) => { setSelected(m); setDrawerTab('detail'); }}
            />
          )}
        </div>

          {/* Drawer */}
        {selectedMedia && (
          <div className="hidden w-80 shrink-0 overflow-y-auto border-l border-[rgba(162,179,229,0.10)] bg-[rgba(6,8,16,0.60)] p-5 lg:flex lg:flex-col">
            <div className="flex items-center justify-between">
              <div className="flex gap-2">
                {(['detail', 'comments', 'likers'] as DrawerTab[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setDrawerTab(t)}
                    className={cn(
                      'cursor-pointer rounded-lg px-2.5 py-1 text-xs font-medium capitalize transition-colors duration-150',
                      drawerTab === t
                        ? 'bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                        : 'text-[#6a7aa0] hover:text-[#c0caf5]',
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                {accountId && <MediaActionsMenu accountId={accountId} media={selectedMedia} />}
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="cursor-pointer text-[#4a5578] transition-colors duration-150 hover:text-[#c0caf5]"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="mt-4 flex-1 space-y-3">
              {drawerTab === 'detail' && (
                <>
                  {selectedMedia.resources[0]?.thumbnailUrl && (
                    <img
                      src={selectedMedia.resources[0].thumbnailUrl}
                      alt=""
                      className="w-full rounded-xl object-cover"
                    />
                  )}
                  <div className="space-y-2 text-sm">
                    <p className="leading-6 text-[#c0caf5]">{selectedMedia.captionText || <span className="italic text-[#4a5578]">No caption</span>}</p>
                    <div className="flex gap-4 text-[#6a7aa0]">
                      <span className="flex items-center gap-1"><Heart className="h-3.5 w-3.5 text-[#f7768e]" /> {selectedMedia.likeCount}</span>
                      <span className="flex items-center gap-1"><MessageCircle className="h-3.5 w-3.5 text-[#7dcfff]" /> {selectedMedia.commentCount}</span>
                    </div>
                    <div className="space-y-1 rounded-xl border border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.02)] p-3 font-mono text-[11px] text-[#6a7aa0]">
                      <p><span className="text-[#4a5578]">id</span> {selectedMedia.mediaId}</p>
                      <p><span className="text-[#4a5578]">code</span> {selectedMedia.code}</p>
                      <p><span className="text-[#4a5578]">type</span> {MEDIA_TYPE_LABEL[selectedMedia.mediaType] ?? selectedMedia.mediaType}</p>
                      {selectedMedia.takenAt && <p><span className="text-[#4a5578]">at</span> {new Date(selectedMedia.takenAt).toLocaleString()}</p>}
                    </div>
                  </div>
                </>
              )}
              {drawerTab === 'comments' && (
                <CommentsPanel accountId={accountId} mediaId={selectedMedia.mediaId} />
              )}
              {drawerTab === 'likers' && (
                <MediaLikersPanel accountId={accountId} mediaId={selectedMedia.mediaId} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
