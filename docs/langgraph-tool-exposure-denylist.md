# LangGraph Tool Exposure Denylist (2026-04-13)

This document records Instagram use-case capabilities that are intentionally
not exposed as LangGraph-callable tools, and why.

## Automated Scanner / CI Contract

This denylist is now enforced by an automated scanner:

- Scanner module: `backend/ai_copilot/audit/coverage_scanner.py`
- Exception manifest: `backend/ai_copilot/audit/coverage_exceptions.json`
- CI gate test: `tests/test_langgraph_audit_coverage_scanner.py`

Run locally:

```bash
./scripts/langgraph-audit-scan.sh --format text
./scripts/langgraph-audit-scan.sh --format json --output artifacts/langgraph-audit-report.json --enforce
```

Notes:

- `--enforce` exits non-zero on unexplained gaps, stale exceptions, or invalid exceptions.
- Report includes `potentially_incomplete: yes/no` when dynamic probes (e.g. optional runtime deps) are unavailable.
- Exception entries must include non-empty `justification`.

## Approved New Exposure Subset

The following previously-missing capabilities are now exposed:

- `search_hashtags`
- `get_hashtag`
- `list_collections`
- `get_media_oembed`
- `get_story`
- `get_highlight`
- `delete_story`
- `mark_stories_seen`
- `change_highlight_title`
- `add_stories_to_highlight`
- `remove_stories_from_highlight`
- `approve_pending_direct_thread`
- `mark_direct_thread_seen`

## Intentionally Non-Exposed Capabilities

### `story.py`

- `get_story_pk_from_url`
  - Rationale: parsing utility only; no authenticated account context needed.
- `publish_story`
  - Rationale: high-complexity payload (file paths, overlays, media-kind validation),
    high side-effect surface, and higher risk of malformed autonomous calls.

### `highlight.py`

- `get_highlight_pk_from_url`
  - Rationale: parsing utility only; no account context required for graph execution flow.

### `direct.py`

- `find_or_create_thread` (numeric `participant_user_ids`)
  - Rationale: numeric-id variant is redundant with safer username-based
    `find_or_create_direct_thread` already exposed.
- `send_to_users` (numeric `user_ids`)
  - Rationale: numeric-id variant is redundant with username-based
    `send_direct_message` already exposed.

### `hashtag.py`

- `get_hashtag_top_posts`
- `get_hashtag_recent_posts`
  - Rationale: both are already available through unified `get_hashtag_posts`
    (with `feed=top|recent`), so direct duplicates are intentionally omitted.

### `collection.py`

- `get_collection_pk_by_name`
  - Rationale: internal helper step already encapsulated by `get_collection_posts`.
- `get_collection_posts` (direct pk-based variant)
  - Rationale: existing `get_collection_posts` tool uses collection name to avoid
    forcing planner to resolve/store numeric collection PKs.

### `media.py`

- No intentional exclusions remain in this module after exposing `get_media_oembed`
  and previously available media read/write tools.
