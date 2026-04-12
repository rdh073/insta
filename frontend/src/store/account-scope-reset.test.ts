import { beforeEach, describe, expect, it } from 'vitest';
import { useDiscoveryStore } from './discovery';
import { useHighlightsStore } from './highlights';
import { useInsightsStore } from './insights';
import { useMediaStore } from './media';

describe('account-scoped store resets', () => {
  beforeEach(() => {
    useMediaStore.setState({
      userId: '',
      scopeAccountId: '',
      media: [],
      selected: null,
      drawerTab: 'detail',
    });
    useHighlightsStore.setState({
      userId: '',
      scopeAccountId: '',
      highlights: [],
      loading: false,
    });
    useDiscoveryStore.setState({
      hashtagInput: '',
      feed: 'top',
      amount: 24,
      scopeAccountId: '',
      hashtag: null,
      posts: [],
      loading: false,
    });
    useInsightsStore.setState({
      postType: 'ALL',
      timeFrame: 'TWO_YEARS',
      ordering: 'REACH_COUNT',
      scopeAccountId: '',
      result: null,
    });
  });

  it('clears media scope state only when account actually changes', () => {
    const media = {
      pk: 1,
      mediaId: 'm1',
      code: 'ABC',
      owner: 'owner',
      captionText: 'caption',
      likeCount: 10,
      commentCount: 2,
      mediaType: 1,
      productType: 'feed',
      takenAt: null,
      resources: [],
    };

    useMediaStore.setState({
      scopeAccountId: 'acct-a',
      media: [media],
      selected: media,
      drawerTab: 'comments',
    });

    useMediaStore.getState().setScopeAccountId('acct-a');
    expect(useMediaStore.getState().media).toHaveLength(1);
    expect(useMediaStore.getState().selected?.mediaId).toBe('m1');

    useMediaStore.getState().setScopeAccountId('acct-b');
    expect(useMediaStore.getState().media).toEqual([]);
    expect(useMediaStore.getState().selected).toBeNull();
    expect(useMediaStore.getState().drawerTab).toBe('detail');
  });

  it('clears highlights when scope account changes', () => {
    useHighlightsStore.setState({
      scopeAccountId: 'acct-a',
      highlights: [
        {
          pk: 'h1',
          highlightId: 'hl1',
          title: 'Old',
          createdAt: null,
          isPinned: null,
          mediaCount: 1,
          latestReelMedia: null,
          ownerUsername: 'owner',
          cover: null,
        },
      ],
      loading: true,
    });

    useHighlightsStore.getState().setScopeAccountId('acct-b');
    expect(useHighlightsStore.getState().highlights).toEqual([]);
    expect(useHighlightsStore.getState().loading).toBe(false);
  });

  it('clears discovery results when account changes', () => {
    useDiscoveryStore.setState({
      scopeAccountId: 'acct-a',
      hashtag: { id: 1, name: 'tag', mediaCount: 10, profilePicUrl: null },
      posts: [
        {
          pk: 1,
          mediaId: 'm1',
          code: 'ABC',
          owner: 'owner',
          captionText: 'caption',
          likeCount: 10,
          commentCount: 2,
          mediaType: 1,
          productType: 'feed',
          takenAt: null,
          resources: [],
        },
      ],
      loading: true,
    });

    useDiscoveryStore.getState().setScopeAccountId('acct-b');
    expect(useDiscoveryStore.getState().hashtag).toBeNull();
    expect(useDiscoveryStore.getState().posts).toEqual([]);
    expect(useDiscoveryStore.getState().loading).toBe(false);
  });

  it('clears insights result when account changes', () => {
    useInsightsStore.setState({
      scopeAccountId: 'acct-a',
      result: {
        count: 1,
        items: [
          {
            mediaPk: 1,
            reachCount: 100,
            impressionCount: 120,
            likeCount: 10,
            commentCount: 2,
            shareCount: 1,
            saveCount: 3,
            videoViewCount: 0,
            extraMetrics: {},
          },
        ],
      },
    });

    useInsightsStore.getState().setScopeAccountId('acct-b');
    expect(useInsightsStore.getState().result).toBeNull();
  });
});
