import { api } from '../client';

type RelationshipResponse = {
  success: boolean;
  action: string;
  target: string;
};

type NotificationResponse = RelationshipResponse & { enabled: boolean };

export type NotificationKind = 'posts' | 'videos' | 'reels' | 'stories';

function cleanUsername(value: string): string {
  return value.trim().replace(/^@/, '');
}

function muteEndpoint(
  accountId: string,
  path: 'mute-posts' | 'unmute-posts' | 'mute-stories' | 'unmute-stories',
  targetUsername: string,
) {
  return api
    .post<RelationshipResponse>(
      `/instagram/relationships/${accountId}/${path}`,
      null,
      { params: { target_username: cleanUsername(targetUsername) } },
    )
    .then((r) => r.data);
}

function notificationToggle(
  accountId: string,
  kind: NotificationKind,
  targetUsername: string,
  enabled: boolean,
) {
  return api
    .post<NotificationResponse>(
      `/instagram/relationships/${accountId}/notifications/${kind}`,
      { target_username: cleanUsername(targetUsername), enabled },
    )
    .then((r) => r.data);
}

export const relationshipsApi = {
  mutePosts: (accountId: string, targetUsername: string) =>
    muteEndpoint(accountId, 'mute-posts', targetUsername),
  unmutePosts: (accountId: string, targetUsername: string) =>
    muteEndpoint(accountId, 'unmute-posts', targetUsername),
  muteStories: (accountId: string, targetUsername: string) =>
    muteEndpoint(accountId, 'mute-stories', targetUsername),
  unmuteStories: (accountId: string, targetUsername: string) =>
    muteEndpoint(accountId, 'unmute-stories', targetUsername),

  setPostsNotifications: (accountId: string, targetUsername: string, enabled: boolean) =>
    notificationToggle(accountId, 'posts', targetUsername, enabled),
  setVideosNotifications: (accountId: string, targetUsername: string, enabled: boolean) =>
    notificationToggle(accountId, 'videos', targetUsername, enabled),
  setReelsNotifications: (accountId: string, targetUsername: string, enabled: boolean) =>
    notificationToggle(accountId, 'reels', targetUsername, enabled),
  setStoriesNotifications: (accountId: string, targetUsername: string, enabled: boolean) =>
    notificationToggle(accountId, 'stories', targetUsername, enabled),
};
