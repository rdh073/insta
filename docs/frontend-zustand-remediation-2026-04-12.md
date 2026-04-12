# Frontend Zustand Remediation Delivery Notes (2026-04-12)

Scope executed: P0/P1 findings from `docs/frontend-zustand-audit-2026-04-12.md` (F-001 through F-007).

## Finding-to-fix mapping

| Finding | Priority | Status | Implemented changes | Regression coverage |
|---|---|---|---|---|
| F-001 — Direct search contract drift | P0 | Fixed (frontend-side normalization) | Added runtime response normalization in `frontend/src/api/instagram/direct.ts` via `parseDirectInboxResult()`. Search payloads with `users[]` now map into synthetic thread rows (`search-user:{id}`), and Direct page resolves them via `findOrCreate` before opening thread details (`frontend/src/pages/DirectPage.tsx`). | `frontend/src/api/instagram/direct.test.ts` (`maps search users payloads to synthetic thread rows`) |
| F-002 — Direct inbox contract drift | P1 | Fixed (frontend-side normalization) | Added legacy inbox compatibility parser in `frontend/src/api/instagram/direct.ts` to normalize `participants: string[]` and `lastMessage: string` into `DirectThreadSummary` + `DirectMessageSummary`. | `frontend/src/api/instagram/direct.test.ts` (`normalizes legacy inbox payloads`) |
| F-003 — Smart Engagement bypasses shared API client | P0 | Fixed | Replaced raw `axios.post` calls with shared `api` client in `frontend/src/api/smart-engagement.ts` and updated page call sites in `frontend/src/pages/SmartEngagementPage.tsx`. | `frontend/src/api/client.test.ts` (interceptor adds `X-API-Key`), `frontend/src/api/smart-engagement.test.ts` (smart engagement methods use shared `api.post`) |
| F-004 — Account error field drift (`error` vs `lastError`) | P1 | Fixed | Canonicalized account error handling to `lastError`/`lastErrorCode` in `frontend/src/types/index.ts`, `frontend/src/store/accounts.ts`, `frontend/src/features/accounts/components/AccountDetail.tsx`, and SSE mapping in `frontend/src/features/accounts/hooks/useAccountEvents.ts`. Added persisted-state migration + legacy compatibility mapping in accounts store (`version: 2`, `migratePersistedAccountsState`). | `frontend/src/store/accounts.test.ts` (`legacy error -> lastError`, migration, updateStatus canonical fields) |
| F-005 — Account picker reconciliation gap | P1 | Fixed | Added reconciliation logic in `frontend/src/components/instagram/AccountPicker.tsx` (`reconcileAccountSelection`) to auto-reconcile invalid/missing selection when active accounts change and prune stale persisted session IDs. | `frontend/src/components/instagram/AccountPicker.test.ts` |
| F-006 — Cross-account state leakage | P0 | Fixed | Added account scope guards in Zustand stores: `scopeAccountId` + `setScopeAccountId` in `media`, `highlights`, `discovery`, `insights` stores. Wired scope updates on account changes in `MediaPage`, `HighlightsPage`, `DiscoveryPage`, `InsightsPage`. Added selected-media validity guard in `MediaPage` render path. | `frontend/src/store/account-scope-reset.test.ts` |
| F-007 — Smart Engagement selected IDs drift | P1 | Fixed | Added selection reconciliation primitives in `frontend/src/store/smartEngagement.ts` (`getValidSelectedIds`, `pruneSelectedIds`, deduped `setSelectedIds`) and updated `SmartEngagementPage` to use valid selected IDs for disabled state, counts, submit validation, and execution payload. | `frontend/src/store/smartEngagement.test.ts` |

## Deferrals

- None. All requested P0/P1 findings were implemented in this remediation pass.

## Validation results

- Type check: `cd frontend && npx tsc --noEmit` ✅
- Tests: `cd frontend && npx vitest run` ✅ (`10` files, `41` tests passed)
