import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import { relationshipsApi, type NotificationKind } from '../../../api/instagram/relationships';
import { ApiError } from '../../../api/client';
import { useRelationshipsStore } from '../../../store/relationships';
import { getErrorMessage } from '../../../lib/error';

export type PendingKey =
  | 'mute_posts'
  | 'mute_stories'
  | `notify_${NotificationKind}`;

export function useRelationshipControls(accountId: string, targetUsername: string) {
  const control = useRelationshipsStore((s) => s.getControl(accountId, targetUsername));
  const setMuted = useRelationshipsStore((s) => s.setMuted);
  const setNotification = useRelationshipsStore((s) => s.setNotification);

  const [pending, setPending] = useState<Set<PendingKey>>(new Set());

  const markPending = useCallback((key: PendingKey, active: boolean) => {
    setPending((prev) => {
      const next = new Set(prev);
      if (active) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  const handle = useCallback(
    async <T,>(
      key: PendingKey,
      action: () => Promise<T>,
      onSuccess: () => void,
      successMessage: string,
      failureMessage: string,
    ) => {
      markPending(key, true);
      try {
        await action();
        onSuccess();
        toast.success(successMessage);
      } catch (err) {
        const message =
          err instanceof ApiError && err.status === 429
            ? 'Rate-limited by Instagram. Try again in a minute.'
            : getErrorMessage(err, failureMessage);
        toast.error(message);
      } finally {
        markPending(key, false);
      }
    },
    [markPending],
  );

  const toggleMutePosts = useCallback(() => {
    const nextMuted = !control.mutedPosts;
    return handle(
      'mute_posts',
      () =>
        nextMuted
          ? relationshipsApi.mutePosts(accountId, targetUsername)
          : relationshipsApi.unmutePosts(accountId, targetUsername),
      () => setMuted(accountId, targetUsername, 'posts', nextMuted),
      nextMuted ? 'Posts muted' : 'Posts unmuted',
      nextMuted ? 'Failed to mute posts' : 'Failed to unmute posts',
    );
  }, [accountId, control.mutedPosts, handle, setMuted, targetUsername]);

  const toggleMuteStories = useCallback(() => {
    const nextMuted = !control.mutedStories;
    return handle(
      'mute_stories',
      () =>
        nextMuted
          ? relationshipsApi.muteStories(accountId, targetUsername)
          : relationshipsApi.unmuteStories(accountId, targetUsername),
      () => setMuted(accountId, targetUsername, 'stories', nextMuted),
      nextMuted ? 'Stories muted' : 'Stories unmuted',
      nextMuted ? 'Failed to mute stories' : 'Failed to unmute stories',
    );
  }, [accountId, control.mutedStories, handle, setMuted, targetUsername]);

  const toggleNotification = useCallback(
    (kind: NotificationKind) => {
      const current = control.notifications[kind];
      const next = !current;
      const setter = {
        posts: relationshipsApi.setPostsNotifications,
        videos: relationshipsApi.setVideosNotifications,
        reels: relationshipsApi.setReelsNotifications,
        stories: relationshipsApi.setStoriesNotifications,
      }[kind];
      return handle(
        `notify_${kind}`,
        () => setter(accountId, targetUsername, next),
        () => setNotification(accountId, targetUsername, kind, next),
        next
          ? `${kind[0].toUpperCase()}${kind.slice(1)} notifications enabled`
          : `${kind[0].toUpperCase()}${kind.slice(1)} notifications disabled`,
        `Failed to toggle ${kind} notifications`,
      );
    },
    [accountId, control.notifications, handle, setNotification, targetUsername],
  );

  return {
    control,
    pending,
    toggleMutePosts,
    toggleMuteStories,
    toggleNotification,
  };
}
