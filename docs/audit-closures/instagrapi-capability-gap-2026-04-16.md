# Audit Closure: instagrapi Capability Gap (2026-04-16)

- Audit date: 2026-04-16
- Closure date: 2026-04-16
- Motivating audit task (Kanban): `68a4d`
- Sibling implementation tasks (Kanban): `94a55`, `289ec`, `bbd43`

## Scope

All public methods exposed by the instagrapi `Client` (https://subzeroid.github.io/instagrapi/usage-guide/) compared against the adapters present in `backend/app/adapters/instagram/` and the ports in `backend/app/application/ports/instagram_*.py`. The audit was triggered by the operator request "find gap implementation" on 2026-04-16 and is recorded under Kanban audit task `68a4d`. This closure document satisfies the mandatory Audit Completion Gate defined in `CLAUDE.md`.

## Evidence

- exa `get_code_context` queries:
  - "instagrapi Client methods overview upload user media direct story hashtag location insights clip album igtv"
  - "instagrapi mixins complete list user_info media_info ..."
- Repo inspection:
  - `backend/app/adapters/instagram/` (24 files enumerated)
  - `backend/app/application/ports/instagram_*.py` (14 port files)
  - `backend/app/application/use_cases/` (use cases enumerated by vertical: account, post, relationship, identity, media, direct, story, highlight, hashtag, location, insight)
- instagrapi docs index pages consulted:
  - `usage-guide/interactions`
  - `usage-guide/media`
  - `usage-guide/direct`
  - `usage-guide/hashtag`
  - `usage-guide/story`
  - `usage-guide/insight`
  - `usage-guide/account`
  - `usage-guide/notes`
  - `usage-guide/challenge`

## Findings

1. Account editing (`set_account_private`, `set_account_public`, `change_profile_picture`, `account_edit`, `set_presence_status`) — zero adapter coverage; profile surface is read-only today. Implication: operators cannot toggle privacy, edit bio/email/phone/url, change avatar, or hide presence from the console.
2. Challenge resolver (`challenge_resolve`, interactive `challenge_code_handler`) — non-interactive stub at `backend/instagram_runtime/auth.py:167-223`; no Clean Architecture surface for operator-submitted codes. Implication: any login that triggers a 6-digit email/SMS challenge fails outright with no remediation path through the API.
3. Direct attachments (`direct_send_photo`, `direct_send_video`, `direct_send_voice`, `direct_media_share`, `direct_story_share`) — only text DMs are supported by `direct_writer.py`. Implication: operators cannot send media-rich DMs or share posts/stories from the console.
4. Notes (`notes_inbox`, `notes_create_text`, `notes_create_video`, `notes_delete`) — no port, no adapter, no use case. Implication: the Notes surface in IG is invisible to the console.
5. Collection writes (`media_save`, `media_unsave`) — explicitly deferred at `backend/app/application/ports/instagram_collections.py:24`. Implication: operators cannot bookmark or unbookmark media programmatically.
6. Media state writes (`media_pin`, `media_unpin`, `media_archive`, `media_unarchive`) — absent despite `media_writer` covering like/unlike. Implication: pinning grid posts and archiving/unarchiving cannot be automated.

Findings confirmed NON-gaps (listed for completeness, no follow-up required):
- Hashtag search and reads — covered by `discovery_reader`.
- Location search and reads — covered by `discovery_reader`.
- Media and comment likes — covered by `media_writer`.
- OTP / 2FA flow — covered (`pyotp` integration).
- Insight reader — covered.
- Story reader — covered.
- Highlight reader and writer — covered.

## Task mapping

| Finding # | Kanban Task ID | Title | Status | Owner |
|---|---|---|---|---|
| 1 | `94a55` | Backend: add account-edit writer (privacy, profile, presence, avatar) | review | unassigned |
| 2 | `289ec` | Backend: add interactive instagrapi challenge resolver (email/SMS code) with operator-facing API | review | unassigned |
| 3 | `bbd43` | Backend: add Direct Messages attachment writer (photo, video, voice, share-media, share-story) | review | unassigned |
| 4 | deferred | Notes (read + create + delete) | deferred | none |
| 5 | deferred | Collection writes (`media_save` / `media_unsave`) | deferred | none |
| 6 | deferred | Media state writes (`media_pin` / `media_unpin` / `media_archive` / `media_unarchive`) | deferred | none |

Justification for deferred entries (findings 4, 5, 6): operator demand is currently low and each capability has a manual workaround in the IG mobile app. Deferring keeps the implementation queue focused on the high-impact gaps (1–3) that have already been filed and shipped to `review`. Any of these can be promoted to a Kanban task on demand without rework, since the relevant ports and adapters do not exist yet (no migration cost).

## Residual risk

What remains uncovered after this closure:

- **Notes (Finding 4):** low operator demand in current workflows; creating drafts is trivial to reintroduce if requested. Risk: operators relying on Notes for outreach signal will not see them in the console.
- **Collection writes (Finding 5) and media pin/archive (Finding 6):** operators can perform these manually in the IG app; blast radius on account ergonomics is low. Risk: bulk operations across many accounts are not automatable.
- **Challenge resolver process-local state (carried by task `289ec`):** if the API process restarts mid-challenge, the in-memory pending-challenge map is lost and the operator must re-trigger login. Documented inside that task; tracked there rather than reopened here.
- **instagrapi surface drift:** instagrapi adds and renames methods between releases. This audit is a point-in-time snapshot against the docs as of 2026-04-16. New gaps may appear as the SDK evolves; the next review (below) is the mitigation.

## Next review date

**2026-07-16** (quarterly cadence). On that date the auditor should rerun the same exa + repo inspection (same query set, same directory enumeration) and refresh this document — adding new findings, closing items that have been implemented since, and re-evaluating the deferred entries against current operator demand.
