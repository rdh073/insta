# Proxy "TRACKED" Count Fix — Validation Note (2026-04-17)

## Linked audit finding

- Audit closure: `docs/audit-closures/frontend-deployed-ui-audit-2026-04-17.md`, finding #8
  ("Proxy page `TRACKED: 0` despite 3 managed accounts").
- Follow-up Kanban task: `proxy-tracked-count-2026-04-17`.

## Root cause

`AccountRoutingTab` previously inlined `accounts.length` to render the "Tracked"
HeaderStat, reading from a local destructured `accounts` variable that was only
loosely coupled to the Zustand store subscription. The Accounts page renders the
same data via its own inline `accounts.length`, so the two metrics were
mechanically computed in separate component closures with no shared definition
of "tracked". This made the Proxy metric easy to diverge from the Accounts page
count (observed as `TRACKED: 0` while `/accounts` showed 3 managed accounts) and
left nothing to unit-test at the store layer.

## Fix

- Added `selectTrackedAccountCount(state)` to `frontend/src/store/accounts.ts`
  as the single source of truth for the managed-account count.
- `AccountRoutingTab` now reads `trackedCount` via
  `useAccountStore(selectTrackedAccountCount)` so the "Tracked" metric
  subscribes to the store through the shared selector and re-renders on every
  `setAccounts` / `upsertAccount` / `removeAccount` mutation.
- Added four unit tests in `frontend/src/store/accounts.test.ts` covering:
  empty store, mixed statuses + proxy assignments, parity with the Accounts
  page denominator, and reactivity to store mutations.

## Automated validation

```bash
cd frontend
npx vitest run src/store/accounts.test.ts
```

Result:

```
Test Files  1 passed (1)
     Tests  8 passed (8)
```

All four new `selectTrackedAccountCount` assertions pass alongside the four
pre-existing migration/normalization tests.

## Manual validation plan

Because the worktree has no live backend attached, the final browser check is
deferred to the reviewer on the deployed environment
(`http://103.253.212.174:3000`) after the PR merges and the server rebuild
completes (`ssh insta "cd /home/insta/instax && git pull && docker compose up -d --build"`).
Steps:

1. Log in with the audit account.
2. Visit `/accounts` — note the "Connected" HeaderStat count (N).
3. Visit `/proxy` → "Account Routing" tab — confirm the "Tracked" HeaderStat
   reads exactly N.
4. Attach a screenshot pairing the two metric tiles (one capture per page) to
   the Kanban task `proxy-tracked-count-2026-04-17`.

## Residual risk

- Still no shared "tracked" selector on `/accounts` — the Accounts page
  continues to inline `accounts.length`. Low risk because both metrics now
  reduce to the same derivation, but a future cleanup could route the Accounts
  page through `selectTrackedAccountCount` as well.
- This fix does not address the upstream hydration timing (AppLayout's
  `waitForBackend` + `setAccounts([])` reset sequence) that was a likely
  proximate cause of the audit-time snapshot. If the audit evidence reappears,
  investigate whether the store is being cleared during route transitions.
