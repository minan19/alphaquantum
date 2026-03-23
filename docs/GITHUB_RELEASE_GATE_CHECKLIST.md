# GitHub Release Gate Checklist

Date: 2026-03-22

Use this checklist once per repository to enforce the CI release gate in GitHub.

## 1) Staging Environment Secret

1. Open repository settings.
2. Go to `Environments` -> `staging`.
3. Add secret:
   - Name: `AQ_STAGING_REDIS_URL`
   - Value: staging Redis endpoint (example: `redis://<host>:6379/0`)
4. Run workflow: `Staging Redis E2E Smoke` (manual `workflow_dispatch`).
5. Verify workflow status is green.
6. (Optional but recommended) Run `Staging Redis Chaos Smoke` manual workflow and verify green.

## 2) Branch Protection Rule

1. Open repository settings.
2. Go to `Branches` -> `Add branch protection rule`.
3. Target branch pattern:
   - `main` (and `master` if used)
4. Enable:
   - `Require a pull request before merging`
   - `Require status checks to pass before merging`
5. Add required check:
   - `Security Gate`
6. Save rule.

## 3) Validation

1. Open any PR to protected branch.
2. Confirm `Security Gate` runs and includes Redis-backed Stage 5.
3. Confirm merge is blocked until `Security Gate` passes.
