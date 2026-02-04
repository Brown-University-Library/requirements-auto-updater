# Plan: avoid tests on rollback

Goal: ensure that when the auto-updater performs any rollback (after a failed `uv sync` or after failed post-update tests), it does **not** execute the target project’s `run_tests.py` **on production servers**.

Rollback verification tests should still run on local and staging/dev.

## Background / current behavior (why this matters)

- `lib/lib_call_runtests.py` already skips `run_initial_tests()` and `run_followup_tests()` when `environment_type == 'production'`.
- However, there is at least one rollback path that **bypasses** this skip logic and runs `run_tests.py` directly.

Observed failure mode from production runs:
- Rollback path triggers `run_tests.py`.
- Django test settings import fails with `KeyError: 'TEST_DATABASES_JSON'`.

The immediate objective of this plan is to ensure rollback paths follow the same policy as the normal test runners:
- on **production**: do not run rollback verification tests
- on **local/staging/dev**: do run rollback verification tests

## Rollback paths to address

1. **Sync-failure rollback inside `UvUpdater.manage_sync()`**

- File: `lib/lib_uv_updater.py`
- Behavior:
  - On `uv sync --upgrade` failure, it restores `uv.lock` from `uv.lock.bak`.
  - Runs `uv sync --frozen ...`.
  - Then runs tests via:
    - `make_run_tests_command(project_path, uv_path)`
    - `run_run_tests_command(...)`
  - This test run occurs regardless of `environment_type` (this is the mismatch to fix).

2. **Post-update-test rollback in `auto_updater.manage_update()`**

- File: `auto_updater.py`
- Behavior:
  - If post-update tests fail (via `run_followup_tests()`), it restores `uv.lock` and runs `uv sync --frozen`.
  - It then calls `run_followup_tests()` again to verify restoration.
  - This path is already skipped on production (because `run_followup_tests()` is skipped).

This plan keeps the verification tests for local/staging/dev, but ensures any rollback-related test execution is skipped on production.

## Proposed changes (implementation plan)

1. **Add a single helper / policy flag for “skip rollback tests on production”**

- Add a clear policy in one place (preferably in `lib/lib_call_runtests.py`) so rollback code reads as intention-revealing.
- Suggested shape: a helper like `should_run_tests(environment_type: str) -> bool` (or `should_run_rollback_tests(environment_type: str) -> bool`) that returns `False` when `environment_type == 'production'`.
- Keep the change minimal: avoid new abstractions unless needed.

2. **Guard test execution in `UvUpdater.manage_sync()` rollback branch**

- File: `lib/lib_uv_updater.py`
- In the `else:  ## revert` block, guard this section so it runs only when `environment_type != 'production'`:
  - `run_tests_command = make_run_tests_command(...)`
  - `run_run_tests_command(...)`
  - `problem_details.append('Error on rollback run_tests() call: ...')`

Replacement behavior:
- If `environment_type == 'production'`, log that rollback verification tests are intentionally skipped.
- If non-production, run tests as currently written and include failure details in the email.
- Continue emailing admins about the sync failure details and the outcome of `uv sync --frozen`.

3. **Keep `auto_updater.manage_update()` rollback verification as-is, but make policy explicit**

- File: `auto_updater.py`
- Current behavior already skips rollback verification tests on production because `run_followup_tests()` exits early for `environment_type == 'production'`.
- When implementing, keep this behavior but ensure logs/emails clearly reflect when tests were skipped due to production policy.

4. **Update email payload structure as needed (keep stable, minimal)**

- If `send_email_of_diffs()` expects `verification_result`, adjust it to accept missing/None (or remove field).
- Keep the rollback email content accurate:
  - “Rollback occurred”
  - “uv.lock restored”
  - “uv sync --frozen attempted” (+ whether it succeeded)
  - “Rollback verification tests skipped on production (by design)”

5. **Update / add focused tests in this repo**

- Add or update unit tests to assert that rollback paths do not invoke `run_run_tests_command()`.

Suggested approach:
- In `tests/test_uv_updater.py`:
  - monkeypatch / mock `run_run_tests_command`.
  - assert it is **not** called when:
    - `run_standard_sync_command()` returns failure, and
    - `environment_type == 'production'`.
  - assert it **is** called when:
    - `run_standard_sync_command()` returns failure, and
    - `environment_type` is `local` or `staging`.
- In `tests/` for `auto_updater.manage_update()` (if present/feasible):
  - mock `run_followup_tests()` to fail, and ensure the rollback path behavior is:
    - production: rollback occurs and verification is skipped
    - non-production: rollback occurs and verification is attempted

## Acceptance criteria

- A failed `uv sync --upgrade` triggers rollback to restore `uv.lock` and runs `uv sync --frozen`.
- On **production**, that rollback does **not** run `run_tests.py`.
- On **local/staging/dev**, that rollback **does** run `run_tests.py`.
- For the post-update test-failure rollback path, production continues to skip rollback verification tests (via existing `run_followup_tests()` behavior), while non-production performs the verification run.
- Logs/emails clearly indicate whether rollback tests were run or skipped due to production policy.
- Repo tests updated to prevent regression.

## Notes for a future work session

- The updater is typically run with `uv run --env-file "../.env" ./auto_updater.py ...`.
- Some target projects’ `run_tests.py` rely on test-only env vars (example: `TEST_DATABASES_JSON`). Avoiding tests on rollback prevents rollback failures caused by missing env config.
- Keep code changes minimal and aligned with `AGENTS.md` (Python 3.12 typing, no nested functions, clarity over cleverness).
