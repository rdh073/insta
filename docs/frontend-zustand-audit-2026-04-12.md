# Frontend Zustand Audit (2026-04-12)

## Scope
Audit target: all frontend Zustand stores/actions/selectors in `frontend/src/store/*` and feature-local Zustand stores in `frontend/src/features/**/store.ts`.

Audit goals:
- Detect contract drift versus backend APIs.
- Detect regressions and missing required state flows.
- Classify findings as `gap`, `regression`, `drift`, or `unimplemented-but-required`.
- Provide prioritized engineering remediation plan.

## Method
- Enumerated all Zustand modules and consumers with `rg`.
- Cross-checked store contracts against:
  - Frontend API clients (`frontend/src/api/**`)
  - Page/feature usage (`frontend/src/pages/**`, `frontend/src/features/**`)
  - Backend route responses (`backend/app/adapters/http/routers/**`)
- Validated frontend compile baseline: `cd frontend && npx tsc --noEmit` (pass).

## Coverage Matrix

| Store | Path | Runtime usage | Primary consumers | Audit status |
|---|---|---|---|---|
| `useAccountStore` | `frontend/src/store/accounts.ts` | Active | `AppLayout`, `AccountsPage`, `DashboardPage`, proxy/relationship features | Finding F-004 |
| `useAccountsUIStore` | `frontend/src/store/accountsUI.ts` | Active | `AccountsPage` | No high-risk finding |
| `useActivityStore` | `frontend/src/store/activity.ts` | Active | `ActivityPage` | No high-risk finding |
| `useCopilotStore` | `frontend/src/store/copilot.ts` | Active | `OperatorCopilotPage` | No high-risk finding |
| `useDirectStore` | `frontend/src/store/direct.ts` | Active | `DirectPage` | Findings F-001, F-002 |
| `useDiscoveryStore` | `frontend/src/store/discovery.ts` | Active | `DiscoveryPage` | Finding F-006 |
| `useHighlightsStore` | `frontend/src/store/highlights.ts` | Active | `HighlightsPage` | Finding F-006 |
| `useInsightsStore` | `frontend/src/store/insights.ts` | Active | `InsightsPage` | Finding F-006 |
| `useLogStreamStore` | `frontend/src/store/logStream.ts` | Active | `LogStreamPage` | No high-risk finding |
| `useMediaStore` | `frontend/src/store/media.ts` | Active | `MediaPage` | Finding F-006 |
| `usePostStore` | `frontend/src/store/posts.ts` | Active | `PostPage`, `CampaignPage`, `usePostJobStream`, `AppLayout` | No high-risk finding |
| `useProxyStore` | `frontend/src/store/proxy.ts` | Active | `ProxyPage` | No high-risk finding |
| `useRelationshipsStore` | `frontend/src/store/relationships.ts` | Active | `RelationshipsPage` | No high-risk finding |
| `useSettingsStore` | `frontend/src/store/settings.ts` | Active | Broad global usage (`api/client`, settings/copilot/pages) | Finding F-003 (integration gap in Smart Engagement API client) |
| `useSmartEngagementStore` | `frontend/src/store/smartEngagement.ts` | Active | `SmartEngagementPage` | Findings F-005, F-007 |
| `useStoriesStore` | `frontend/src/store/stories.ts` | Dormant in routing | `StoriesPage` only | Finding F-008 |
| `useTemplateStore` | `frontend/src/store/templates.ts` | Active | `TemplatesPage`, `PostPage` | No high-risk finding |
| `useRelationshipStore` | `frontend/src/features/relationships/store.ts` | Active | relationships hooks (`useFollowAction`) | No high-risk finding |

## Findings

### F-001 — Direct Search Contract Drift Breaks Thread Results
- Category: `drift`
- Severity: `Critical`
- Priority: `P0`
- Impacted paths:
  - `frontend/src/api/instagram/direct.ts`
  - `frontend/src/pages/DirectPage.tsx`
  - `frontend/src/types/instagram/direct.ts`
  - `backend/app/adapters/http/routers/instagram/direct.py`
- Expected behavior:
  - `searchThreads()` returns `DirectInboxResult` with `threads: DirectThreadSummary[]`, so Direct page can render/search thread list safely.
- Actual behavior:
  - Backend search endpoint returns `{ users: [...] }`, while frontend expects `{ threads: [...] }`.
  - UI calls `setThreads(result.threads)` and then renders `threads.map(...)`.
- Reproduction path:
  1. Open Direct page.
  2. Pick active account.
  3. Type any query into thread search input.
  4. Search response has no `threads`; store receives `undefined`; thread render path can break.
- Risk:
  - Thread search is non-functional and can trigger runtime errors in DM workflow.
- Recommended fix direction:
  - Normalize API contract to one shape.
  - Preferred: backend `GET /direct/{account_id}/search` returns `threads` using existing `_to_direct_thread_summary` mapping.
  - Alternative: frontend introduces explicit `DirectSearchResult` and maps users to thread-like UI model.
- Evidence:
  - `frontend/src/api/instagram/direct.ts:37-40`
  - `frontend/src/pages/DirectPage.tsx:182-183`
  - `backend/app/adapters/http/routers/instagram/direct.py:291-295`

### F-002 — Direct Inbox Contract Drift Degrades Thread Rows
- Category: `drift`
- Severity: `High`
- Priority: `P1`
- Impacted paths:
  - `frontend/src/types/instagram/direct.ts`
  - `frontend/src/pages/DirectPage.tsx`
  - `backend/app/adapters/http/routers/instagram/direct.py`
- Expected behavior:
  - Inbox `threads[]` payload should match `DirectThreadSummary` (`participants` objects, `lastMessage` object).
- Actual behavior:
  - Inbox route serializes `participants` as `string[]` and `lastMessage` as `string | null`.
  - UI expects `participants[].username` and `lastMessage.text`.
- Reproduction path:
  1. Open Direct page and load inbox.
  2. Observe participant names/preview text inconsistent or empty (`@undefined`, preview fallback).
- Risk:
  - Misleading DM thread display; latent runtime risk as UI evolves.
- Recommended fix direction:
  - Replace custom inbox serialization with `_to_direct_thread_summary()` to enforce identical shape across inbox/pending/thread detail/search.
- Evidence:
  - `frontend/src/types/instagram/direct.ts:15-20`
  - `frontend/src/pages/DirectPage.tsx:23-24`
  - `backend/app/adapters/http/routers/instagram/direct.py:197-201`

### F-003 — Smart Engagement API Bypasses Auth/Header Interceptors
- Category: `regression`
- Severity: `Critical`
- Priority: `P0`
- Impacted paths:
  - `frontend/src/api/smart-engagement.ts`
  - `frontend/src/api/client.ts`
  - `backend/app/main.py`
- Expected behavior:
  - Smart Engagement requests should use shared API client so `X-API-Key` and dashboard bearer token are injected consistently.
- Actual behavior:
  - Smart Engagement API uses raw `axios.post`, bypassing interceptor-based auth headers.
  - Backend middleware enforces API key when `API_KEY` is configured.
- Reproduction path:
  1. Configure backend with `API_KEY`.
  2. Run Smart Engagement from UI.
  3. Requests to `/api/ai/smart-engagement/*` fail with unauthorized responses.
- Risk:
  - Feature hard-fails in secured environments despite valid settings.
- Recommended fix direction:
  - Refactor `smartEngagementApi` to use shared `api` instance.
  - Remove optional manual base URL arg or explicitly set `baseURL` on shared client call path.
- Evidence:
  - `frontend/src/api/smart-engagement.ts:63,72`
  - `frontend/src/api/client.ts:23-33`
  - `backend/app/main.py:229-265`

### F-004 — Account Error Field Drift (`error` vs `lastError`)
- Category: `drift`
- Severity: `High`
- Priority: `P1`
- Impacted paths:
  - `frontend/src/types/index.ts`
  - `frontend/src/store/accounts.ts`
  - `frontend/src/features/accounts/components/AccountDetail.tsx`
  - `frontend/src/features/accounts/hooks/useAccountEvents.ts`
  - `backend/app/adapters/http/routers/accounts.py`
- Expected behavior:
  - One canonical error field should be used end-to-end for account status/error rendering.
- Actual behavior:
  - Backend list serialization uses `lastError`/`lastErrorCode`.
  - Store updater `updateStatus()` writes `error`.
  - Relogin success patch updates `lastError` fields.
  - UI renders `account.error` only.
- Reproduction path:
  1. Trigger relogin failure, then success, then refresh page.
  2. Observe inconsistent error visibility/clearing between in-memory and rehydrated account payloads.
- Risk:
  - Stale or missing operator error context; incorrect account-state diagnosis.
- Recommended fix direction:
  - Standardize on `lastError` + `lastErrorCode` in frontend domain type/store/UI.
  - Add compatibility mapping for legacy `error` during migration window.
  - Update SSE payload handling to map backend keys consistently.
- Evidence:
  - `frontend/src/types/index.ts:6,14-15`
  - `frontend/src/store/accounts.ts:50-54`
  - `frontend/src/features/accounts/components/AccountDetail.tsx:73,102,169-171`
  - `frontend/src/features/accounts/hooks/useAccountEvents.ts:67`
  - `backend/app/adapters/http/routers/accounts.py:179-180,195-196`

### F-005 — Account Picker Missing Reconciliation After Async Account Hydration
- Category: `unimplemented-but-required`
- Severity: `Medium`
- Priority: `P1`
- Impacted paths:
  - `frontend/src/components/instagram/AccountPicker.tsx`
- Expected behavior:
  - If no selection exists, account picker should auto-select a valid active account whenever active account list becomes available or changes.
- Actual behavior:
  - Both component and hook initialization are one-shot (`[]` effect / initial state only), so empty selections can remain after async account hydration.
- Reproduction path:
  1. Load page with no active accounts initially.
  2. Accounts hydrate shortly after (or become active via relogin).
  3. Picker options show accounts, but selected value can remain empty.
- Risk:
  - Action buttons appear usable but no account context is selected, creating no-op or confusing errors.
- Recommended fix direction:
  - Add reconciliation effect keyed to `active` list + current `accountId`, with guard against clobbering explicit user choices.
  - Ensure invalid persisted ID is evicted when account no longer active.
- Evidence:
  - `frontend/src/components/instagram/AccountPicker.tsx:20-25,57-60`

### F-006 — Cross-Account State Leakage in Account-Scoped Stores
- Category: `gap`
- Severity: `Critical`
- Priority: `P0`
- Impacted paths:
  - `frontend/src/pages/MediaPage.tsx`
  - `frontend/src/pages/HighlightsPage.tsx`
  - `frontend/src/pages/DiscoveryPage.tsx`
  - `frontend/src/pages/InsightsPage.tsx`
  - `frontend/src/store/media.ts`
  - `frontend/src/store/highlights.ts`
  - `frontend/src/store/discovery.ts`
  - `frontend/src/store/insights.ts`
- Expected behavior:
  - Account-scoped data should be cleared/revalidated on account change before action execution.
- Actual behavior:
  - Account switch changes `accountId`, but loaded entities/results from prior account remain in store.
  - In `MediaPage` and `HighlightsPage`, destructive actions are executed with new `accountId` against stale selected entities.
- Reproduction path:
  1. Load media/highlights for Account A.
  2. Switch picker to Account B.
  3. Without reloading list, perform comment/delete/rename actions from stale UI.
- Risk:
  - Incorrect account-target pairing in destructive workflows; data integrity and operator trust risk.
- Recommended fix direction:
  - On account change, call clear/reset actions (`clearMedia`, `clearHighlights`, `clearResults`, `setResult(null)`) and clear selected entities.
  - Add runtime guards before destructive calls to ensure entity belongs to current account context.
- Evidence:
  - `frontend/src/pages/MediaPage.tsx:376,436-492`
  - `frontend/src/pages/HighlightsPage.tsx:191,221-227`
  - `frontend/src/pages/DiscoveryPage.tsx:154,185-244`
  - `frontend/src/pages/InsightsPage.tsx:133,150-180`

### F-007 — Smart Engagement Selected Account IDs Drift From Active Accounts
- Category: `gap`
- Severity: `High`
- Priority: `P1`
- Impacted paths:
  - `frontend/src/store/smartEngagement.ts`
  - `frontend/src/pages/SmartEngagementPage.tsx`
- Expected behavior:
  - Persisted selected IDs should be reconciled with current active accounts before enabling run actions.
- Actual behavior:
  - `selectedIds` is persisted and not pruned against current active account set.
  - Submit checks only `selectedIds.length`; actual execution uses `activeAccounts.filter(selectedIds)` which can be empty.
  - Run button `disabled` logic also uses raw `selectedIds.length`.
- Reproduction path:
  1. Persist selected IDs from previous session.
  2. Those accounts become inactive/removed.
  3. Run button stays enabled; execution runs 0 accounts with unclear UX feedback.
- Risk:
  - Silent no-op execution and operator confusion; unreliable engagement workflow.
- Recommended fix direction:
  - Compute `validSelectedIds = selectedIds ∩ activeAccountIds` in derived selector/effect.
  - Disable submit when `validSelectedIds.length === 0`.
  - Auto-prune stale persisted IDs on mount/account list change.
- Evidence:
  - `frontend/src/store/smartEngagement.ts:43,67-72`
  - `frontend/src/pages/SmartEngagementPage.tsx:408-423,586-589`

### F-008 — Stories Zustand Module Is Implemented But Not Reachable
- Category: `unimplemented-but-required`
- Severity: `Low`
- Priority: `P2`
- Impacted paths:
  - `frontend/src/store/stories.ts`
  - `frontend/src/pages/StoriesPage.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/components/layout/Sidebar.tsx`
- Expected behavior:
  - If stories store/page is in active product scope, route and navigation should expose it.
- Actual behavior:
  - `/stories` route redirects to `/accounts`; Stories page/store remain in code but unreachable from runtime navigation.
- Reproduction path:
  1. Navigate to `/stories`.
  2. App redirects to `/accounts`.
  3. No sidebar entry exists for stories.
- Risk:
  - Dead-state module drift; maintenance overhead and false sense of feature completeness.
- Recommended fix direction:
  - Decide product intent:
    - Re-enable route + nav and validate feature end-to-end, or
    - Remove dormant page/store/API exports to reduce drift surface.
- Evidence:
  - `frontend/src/store/stories.ts:12-20`
  - `frontend/src/pages/StoriesPage.tsx:81-84`
  - `frontend/src/App.tsx:101`
  - `frontend/src/components/layout/Sidebar.tsx:58-65`

## Prioritized Remediation Plan

### P0 (Immediate)
1. Fix Direct API contract alignment for search and inbox (F-001, F-002).
   - Task: unify backend direct serializers via mapper helpers (`_to_direct_thread_summary`) for inbox/search.
   - Task: add FE runtime decode guards in `directApi` to fail fast with actionable errors if response shape drifts.
   - Task: verify `DirectPage` search + inbox thread rendering and selection flows.
2. Fix Smart Engagement auth/header bypass (F-003).
   - Task: migrate `smartEngagementApi` to shared `api` client.
   - Task: add test coverage for API-key secured mode (request includes `X-API-Key`).
3. Add account-switch reset guards for account-scoped destructive flows (F-006).
   - Task: add account-change effects in `MediaPage` and `HighlightsPage` to clear stale entities.
   - Task: add preflight validation before destructive actions (`selected` entity validity + account consistency).

### P1 (Near-term)
1. Canonicalize account error fields and migration path (F-004).
   - Task: replace frontend `error` usage with `lastError`/`lastErrorCode`.
   - Task: add one migration utility for persisted account payloads.
   - Task: update `useAccountEvents` patch mapping.
2. Add robust account picker reconciliation behavior (F-005).
   - Task: reconcile current selection whenever active account list changes.
   - Task: remove stale persisted session selection IDs.
3. Reconcile Smart Engagement persisted selection with active accounts (F-007).
   - Task: derive `validSelectedIds` and use it for button disabled state, summary badges, and submit payload.
   - Task: auto-prune stale IDs when accounts list updates.

### P2 (Backlog hygiene)
1. Resolve Stories feature intent and reduce drift (F-008).
   - Task: either re-enable route/nav and QA it, or remove dormant store/page references.

## Suggested Validation Checklist After Remediation
- Direct inbox/search responses validate against one DTO contract and render without runtime warnings.
- Smart Engagement works when backend `API_KEY` is set.
- Switching account in media/highlights/discovery/insights clears prior account artifacts.
- Account errors display consistently before and after refresh/relogin/SSE updates.
- Picker always lands on a valid active account when available.
- Smart Engagement run button state matches valid selected active accounts only.
- Stories feature is either live and reachable or fully removed.
- Audit completion is blocked until an `audit-closure` document is published with scope, evidence, findings, task mapping, residual risk, and next review date.
