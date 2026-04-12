# ChallengeRequired Audit Baseline (Active)

Date: 2026-04-12
Scope: auth/login, relogin mode selection, account hydration/connectivity status mapping, exception catalog/runtime drift.

## Sources

- Context7 / upstream docs:
  - https://github.com/subzeroid/instagrapi/blob/master/docs/usage-guide/handle_exception.md
  - https://github.com/subzeroid/instagrapi/blob/master/docs/usage-guide/challenge_resolver.md
  - https://subzeroid.github.io/instagrapi/usage-guide/handle_exception
  - https://subzeroid.github.io/instagrapi/usage-guide/challenge_resolver
- Codebase and runtime evidence:
  - `backend/instagram_runtime/auth.py`
  - `backend/app/application/use_cases/account_auth.py`
  - `backend/app/application/use_cases/account_connectivity.py`
  - `frontend/src/pages/AccountsPage.tsx`
  - `frontend/src/features/accounts/components/AccountDetail.tsx`
  - `backend/app/adapters/instagram/exception_catalog/specs/challenge.py`
  - `backend/app/adapters/instagram/exception_catalog/registry.py`
  - `backend/app/adapters/instagram/exception_catalog/documented_names.py`
  - `backend/app/adapters/instagram/exception_handler.py`
  - `backend/requirements.txt`
  - `backend/.venv/lib/python3.12/site-packages/instagrapi/mixins/private.py`
  - `backend/.venv/lib/python3.12/site-packages/instagrapi/exceptions.py`
  - `tests/conftest.py`
  - `backend/tests/conftest.py`

## Validated Findings

1. Implicit challenge flow can block in backend runtime.
   - `new_client()` and auth client creation do not set `client.handle_exception` or `client.challenge_code_handler` in `backend/instagram_runtime/auth.py`.
   - In `instagrapi 2.3.0`, `PrivateRequestMixin.handle_exception = None` and `challenge_code_handler = manual_input_code`, where `manual_input_code()` uses `input()` (`instagrapi/mixins/private.py`).
   - `private_request()` auto-calls `challenge_resolve()` when `handle_exception` is unset and exception is `ChallengeRequired` (`instagrapi/mixins/private.py`).
   - Result: in non-interactive backend execution, challenge flow can hang waiting on stdin or fail with EOF instead of cleanly surfacing a structured challenge failure.

2. Status drift exists between hydration and connectivity for challenge-family failures.
   - Background hydration sets status `"error"` for any `requires_user_action` (`backend/app/application/use_cases/account_auth.py`).
   - Connectivity probe maps `failure.family == "challenge"` to status `"challenge"` (`backend/app/application/use_cases/account_connectivity.py`).
   - Result: identical underlying challenge conditions can appear as `"error"` in one path and `"challenge"` in another.

3. Prefix-based error-code checks create challenge-family blind spots.
   - Relogin mode selection uses `code.startswith("challenge")` (`backend/app/application/use_cases/account_auth.py`).
   - Frontend relogin UI logic uses `code.startsWith("challenge")` (`frontend/src/pages/AccountsPage.tsx`, `frontend/src/features/accounts/components/AccountDetail.tsx`).
   - Challenge-family catalog includes non-`challenge*` codes such as `consent_required`, `geo_blocked`, `checkpoint_required` (`backend/app/adapters/instagram/exception_catalog/specs/challenge.py`).
   - Result: challenge-family failures can be misrouted as generic errors when code prefix is not `challenge`.

4. Runtime/catalog/test drift confirmed for `instagrapi==2.3.0`.
   - Project pins `instagrapi==2.3.0` (`backend/requirements.txt`).
   - Runtime has `CaptchaChallengeRequired` (`instagrapi/exceptions.py`) but it is absent from `documented_names.py` and `registry.py`.
   - Current handler falls back to base-class mapping and classifies `CaptchaChallengeRequired` as `client_error` / `common_client` (via `ClientError` mapping path in `exception_handler.py` + registry).
   - Root and backend test stubs define only minimal exception set and omit challenge-family classes (`tests/conftest.py`, `backend/tests/conftest.py`), leaving challenge edge cases under-tested.

## Patch Acceptance Criteria

1. Explicit non-interactive challenge handling is wired at client creation.
   - `new_client()` sets both `handle_exception` and `challenge_code_handler`.
   - No backend auth flow may call blocking stdin `input()` under any challenge path.
   - Challenge-related login failures surface as structured failures (code/family/message), not hangs/EOF-only crashes.
   - Tests cover challenge exception paths in login + relogin with no interactive input.

2. Status mapping semantics are unified across auth hydration and connectivity.
   - A single rule is used for status derivation from `InstagramFailure` in both paths.
   - Any `failure.family == "challenge"` is persisted as `"challenge"` (not `"error"`).
   - `requires_user_action` alone is not allowed to force `"error"` when family indicates challenge.
   - Tests assert same failure payload yields same status regardless of call path.

3. Challenge routing no longer depends on `startswith("challenge")`.
   - Backend relogin mode selection uses family-aware logic (or an explicit challenge code set), not prefix matching.
   - Frontend challenge UX decisions use server status/family or a shared challenge classifier, not prefix checks.
   - Tests include at least `challenge_required`, `checkpoint_required`, `consent_required`, and `geo_blocked` (or equivalent mapped family cases) and assert challenge workflow behavior.

4. Exception catalog covers runtime challenge classes and guards against drift.
   - `CaptchaChallengeRequired` is explicitly classified into the intended challenge-family behavior (not generic `client_error`).
   - Catalog/runtime completeness test fails when runtime exception classes drift outside registered/documented coverage without explicit allowlist.
   - Test stubs include challenge-family exceptions used by auth/connectivity logic, or tests run against real `instagrapi` classes in coverage-critical cases.

5. Operator-visible API behavior remains stable and deterministic.
   - `last_error_code` and status returned from relogin/connectivity endpoints are consistent with family classification.
   - No path returns `"active"` while challenge/manual action is unresolved.
   - SSE/background hydration updates do not silently downgrade challenge-family failures to generic error status.
