# Audit Closure: Relationship Mutes + Notification Toggles (2026-04-17)

- Audit date: 2026-04-17
- Closure date: 2026-04-17
- Motivating audit task: "mute suite + notification toggles missing from relationship writer"
- Parent audit: `docs/audit-closures/instagrapi-deep-gap-2026-04-17.md` (findings follow-up)

## Scope

Close the gap documented in the 2026-04-17 instagrapi deep-gap audit regarding per-user feed controls:

- Mute pair: `mute_posts_from_follow` / `unmute_posts_from_follow`
- Story mute pair: `mute_stories_from_follow` / `unmute_stories_from_follow`
- Notification toggle pairs for posts / videos / reels / stories (8 methods)

Block/unblock (`user_block` / `user_unblock`) was investigated as part of this task. The user-facing instagrapi 2.3.0 docs (`https://subzeroid.github.io/instagrapi/usage-guide/user.html`) do not list block/unblock as a supported public method, so it is intentionally excluded from this closure; reintroduction would require an explicit scope bump and a new audit finding.

## Evidence

- exa `get_code_context` — "instagrapi mute_posts_from_follow notifications user_posts_notifications enable disable" — confirmed the public docs table listing the four mute methods and eight notification-toggle methods.
- exa `crawling_exa` on `https://raw.githubusercontent.com/subzeroid/instagrapi/master/instagrapi/mixins/user.py` — confirmed the exact signatures:
  - `mute_posts_from_follow(user_id, revert=False)`, `unmute_posts_from_follow(user_id)`
  - `mute_stories_from_follow(user_id, revert=False)`, `unmute_stories_from_follow(user_id)`
  - `enable_posts_notifications(user_id, disable=False)`, `disable_posts_notifications(user_id)`
  - `enable_videos_notifications(user_id, revert=False)`, `disable_videos_notifications(user_id)`
  - `enable_reels_notifications(user_id, revert=False)`, `disable_reels_notifications(user_id)`
  - `enable_stories_notifications(user_id, revert=False)`, `disable_stories_notifications(user_id)`
- Instagram help center pages for mute/unmute UX: `https://help.instagram.com/290238234687437/`, `https://help.instagram.com/469042960409432`.

## Findings

1. `InstagramRelationshipWriter` port was missing 12 operations: mute_posts, unmute_posts, mute_stories, unmute_stories, plus `set_{posts,videos,reels,stories}_notifications(enabled: bool)` toggles.
2. Adapter methods did not delegate to instagrapi's mute/notification mixin.
3. The relationships HTTP router only exposed follow / unfollow / remove-follower / close-friends endpoints.
4. The frontend had no UI surface for either the mute or notification toggles.

## Task mapping

| Finding # | Description | Status | Location |
|---|---|---|---|
| 1 | Extend `InstagramRelationshipWriter` port | done | `backend/app/application/ports/instagram_relationship_writer.py` |
| 2 | Extend adapter with rate-limit-aware error translation | done | `backend/app/adapters/instagram/relationship_writer.py` |
| 3 | Add HTTP endpoints (`mute-posts`, `unmute-posts`, `mute-stories`, `unmute-stories`, `notifications/{kind}`) | done | `backend/app/adapters/http/routers/instagram/relationships.py` |
| 4 | Frontend API, store, and per-user controls feature | done | `frontend/src/api/instagram/relationships.ts`, `frontend/src/store/relationships.ts`, `frontend/src/features/relationships/components/UserRelationshipControls.tsx`, `frontend/src/features/relationships/components/UserControlsTab.tsx`, `frontend/src/features/relationships/hooks/useRelationshipControls.ts` |
| 5 | LangGraph coverage manifest — declare the five new use-case methods as deliberately operator-only (UI-driven, not AI-tool-exposed) | done | `backend/ai_copilot/audit/coverage_exceptions.json` |

## Residual risk

- Block/unblock remains unaddressed; the audit found no public instagrapi 2.3.0 surface for those operations. If operators require them, file a new audit.
- The frontend UI tracks optimistic state locally but does not reconcile with Instagram's canonical state on page load. A future enhancement could hydrate from a read endpoint once instagrapi exposes a friendship mute/notification reader.
- Rate-limit behavior was covered by unit tests (adapter 429 path per method); production behavior under sustained 429 cooldowns is covered by the shared `rate_limit_guard` used by every relationship write.

## Next review date

2026-07-17 (quarterly review cadence).
