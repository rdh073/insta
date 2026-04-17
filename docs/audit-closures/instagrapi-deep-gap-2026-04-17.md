# Audit Closure: instagrapi Deep-Gap Drift Review (2026-04-17)

- Audit date: 2026-04-17
- Closure date: 2026-04-17
- Motivating audit task (Kanban): instagrapi deep-gap drift review
- Sibling implementation tasks: direct writer vendor-contract pinning (this PR)

## Scope

Second-pass audit of the Instagram direct writer adapter against the
canonical instagrapi 2.3.0 source. Focus: call sites where a vendor version
bump, doc/source mismatch, or type-coercion relaxation could silently change
behavior without a failing test.

In scope:
- `backend/app/adapters/instagram/direct_writer.py:78-113` (`send_to_thread`)
- `backend/app/adapters/instagram/direct_writer.py:45-76, 407-461`
  (`find_or_create_thread` and dict-branch mapping helpers)
- `backend/requirements.txt:4` (`instagrapi==2.3.0`)
- instagrapi usage guide: <https://subzeroid.github.io/instagrapi/usage-guide/direct.html>

Out of scope:
- Direct reader adapter drift (tracked separately).
- Attachment/share paths (covered by `test_direct_attachments.py`).

## Evidence

- Installed instagrapi 2.3.0 source (`/home/xtrzy/.local/lib/python3.12/site-packages/instagrapi/mixins/direct.py`):
  - `:366` — `def direct_answer(self, thread_id: int, text: str) -> DirectMessage:`
  - `:818` — `def direct_thread_by_participants(self, user_ids: List[int]) -> Dict:`
    (returns a raw dict, not a `DirectThread` model)
- exa `get_code_context` + `crawling_exa` of the official usage guide:
  - `direct_answer(thread_id: int, text: str) → DirectMessage | Add Message to exist Thread`
  - `direct_thread_by_participants(user_ids: List[int]) → DirectThread | Get thread by user_id`
- Observation: the usage guide advertises `direct_thread_by_participants` as
  returning `DirectThread`, but the installed 2.3.0 source returns a raw dict.
  The adapter already guards both shapes via
  `_map_find_or_create_thread_response`; the drift risk is that a future
  release flips the default shape in either direction, silently breaking the
  un-tested branch.

## Findings

1. **Call-shape drift risk on `direct_answer`**: the adapter coerces
   `int(direct_thread_id)` before calling the vendor. The canonical signature
   requires `int`. No test previously pinned the int form of the call, so a
   local refactor that drops the coercion (or a vendor bump that relaxes to
   `str | int`) could have silently shipped.
2. **Dual-shape response drift risk on `direct_thread_by_participants`**:
   dict and model branches of `_map_find_or_create_thread_response` existed
   but were only partially covered. The new test file pins both branches and
   adds a structural-contract parity test so the two paths cannot diverge.
3. **Test-suite self-drift**: six pre-existing tests in
   `backend/tests/test_instagram_direct.py` passed non-numeric thread ids
   (`"thread-1"`, `"msg-1"`) to methods that call `int()` at the vendor
   boundary. They were failing silently under `pytest backend/tests/`.
   Tests corrected to use numeric-string ids.

## Task mapping

| Finding # | Kanban Task ID | Title | Status | Owner |
|---|---|---|---|---|
| 1 | this-pr | Pin `direct_answer` canonical int signature | review | Xtrzy |
| 2 | this-pr | Pin dict/model dual-shape contract for `direct_thread_by_participants` | review | Xtrzy |
| 3 | this-pr | Fix `"thread-1"`-style invalid thread ids in existing direct tests | review | Xtrzy |

## Residual risk

- Other adapters (reader, attachments) could share the same int-coercion
  pattern without regression tests. A follow-up audit should sweep the
  remaining direct/story/media writers for identical drift seams.
- The `direct_thread_by_participants` online docs vs. installed-source
  mismatch is unresolved upstream; the adapter guards both shapes, but the
  adapter fix is only as good as the guarded-shape test coverage.

## Next review date

2026-07-17 (quarterly) — or sooner if `backend/requirements.txt:4` bumps
`instagrapi` past 2.3.0.
