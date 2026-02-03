# Plan: Fix missing error-email on `uv sync` failure

## Goal
Ensure an error-email is sent when `uv sync ...` fails (non-zero exit), without addressing the underlying `uv sync` failure itself.

## What I reviewed
- `requirements-auto-updater/README.md`
- `requirements-auto-updater/AGENTS.md`
- `requirements-auto-updater/auto_updater.py`
- `requirements-auto-updater/lib/lib_uv_updater.py`
- `requirements-auto-updater/lib/lib_emailer.py`
- `requirements-auto-updater/lib/lib_environment_checker.py`
- `requirements-auto-updater/lib/lib_call_runtests.py`
- Tests under `requirements-auto-updater/tests/`

## Observed behavior (from the log snippet)
- `UvUpdater.manage_sync()` runs `uv sync --upgrade ...`.
- The `uv` subprocess returns `returncode=2`.
- The code logs:
  - `problem / uv sync failed`
  - then attempts a rollback via `uv sync --frozen ...`
- No error-email is sent.

## Why no error-email was sent
### 1) The `uv sync` failure path does not send email
In `lib/lib_uv_updater.py`, `UvUpdater.manage_sync()` sets `problem_message = 'problem / uv sync failed'` and then contains an explicit TODO:

- `# email_admins_with_errors(problem_message)  # TODO`

So the failure path is currently **missing the email send entirely**.

### 2) `manage_sync()` neither raises nor returns failure status to `manage_update()`
`auto_updater.manage_update()` calls:

- `uv_updater.manage_sync(uv_path, project_path, environment_type)`

…but `manage_sync()` always returns `None`, regardless of success/failure.

So even if `uv sync` fails (and rollback is attempted), `manage_update()` continues into:

- `compare_uv_lock_files()`

If the lock file was restored (or never changed), `compare_result['changes']` will be `False`, and **no diff-email is sent**. That yields a silent failure.

### 3) The `uv sync` failure path appears incomplete / brittle
Inside `UvUpdater.manage_sync()`, after the frozen sync rollback, the code calls:

- `self.make_run_tests_command(...)`
- `self.run_run_tests_command(...)`

Those methods do **not** exist on `UvUpdater` (the working implementations live in `lib/lib_call_runtests.py`).

This means the failure-handling path is at risk of raising `AttributeError` before it ever reaches any future email call you might add later (unless the email is sent earlier, or rollback is wrapped defensively).

### 4) (Not fixing, but relevant context) group naming mismatch explains *why* `uv sync` failed
The log shows:

- `error: Group \`production\` is not defined in the project's \`dependency-groups\` table`

Two repo facts matter:
- `validate_pyproject_toml()` currently requires dependency-group keys `staging` and `prod`.
- `UvUpdater.make_sync_command()` uses groups `local`, `staging`, and `production`.

So a project that defines `[dependency-groups].prod` (as required by validation) but **not** `[dependency-groups].production` will pass validation, then fail at runtime.

Per your instruction, this plan does **not** address that underlying cause; it’s just useful context for reproducing the error path.

## Expected behavior (proposed)
On any `uv sync` failure during the update phase:
- Attempt rollback **best-effort** (restore `uv.lock`, run frozen sync, optionally re-run tests).
- Send an error email to `project_email_addresses` (or sys-admins if project addresses are unavailable, consistent with existing patterns).
- Stop further processing (raise an exception or return a status that `manage_update()` treats as fatal).

## Plan to implement (future work session)
### A) Make `uv sync` failures visible to the manager function
- **Change** `UvUpdater.manage_sync(...)` to return a structured result, e.g.
  - `tuple[bool, dict[str, str]]` (matches the existing `(ok, output)` convention used elsewhere), or
  - raise an exception after emailing.

Recommendation (smallest change consistent with repo patterns):
- Email inside `manage_sync()` (because it has the best context for the `uv` subprocess output).
- Then raise an exception so `manage_update()` halts immediately.

### B) Give `manage_sync()` access to recipients
Right now `UvUpdater.manage_sync()` does not receive `project_email_addresses`, so it cannot follow the repo’s existing “function sends its own email on failure” pattern.

- **Update signature**:
  - from: `manage_sync(self, uv_path: Path, project_path: Path, environment_type: str) -> None`
  - to: `manage_sync(self, uv_path: Path, project_path: Path, environment_type: str, project_email_addresses: list[tuple[str, str]]) -> None`

- **Update call-site** in `auto_updater.manage_update()` accordingly.

### C) Implement the email send in the failure path
Use existing infrastructure:
- `from lib.lib_emailer import Emailer`
- `emailer = Emailer(project_path)`

Message format options:
- **Option 1 (minimal / consistent):** Use `emailer.create_setup_problem_message(...)` with a clear message that this is an update-phase failure.
- **Option 2 (clearer UX):** Add a new `Emailer.create_sync_problem_message(...)` (preferred long-term), but this is a bigger change.

The message should include:
- The exact command attempted (`sync_command`)
- `returncode`, `stdout`, `stderr` from the failing subprocess
- Any rollback attempt results (including failures)

Important: send email **even if rollback steps fail** (don’t let rollback exceptions suppress the notification).

### D) Make rollback logic safe enough to not suppress the email
Because the failure path currently references non-existent `UvUpdater` methods, do one of:
- **Minimal:** send the email immediately after detecting the failure, before rollback logic.
- **Better:** fix the rollback calls to use `lib_call_runtests.make_run_tests_command()` and `lib_call_runtests.run_run_tests_command()` (or call `run_followup_tests()` / `run_initial_tests()` as appropriate).

This rollback robustness work is in-scope because it directly affects whether the error-email path can run reliably.

### E) Add/extend tests to prevent regression
Add a new unit test to `tests/test_uv_updater.py` that verifies an email attempt happens on sync failure.

Test approach (mirrors existing mocking patterns in `tests/test_environment_checks.py`):
- Build a temp project directory containing `uv.lock` and `uv.lock.bak`.
- Patch:
  - `subprocess.run` to return `CompletedProcess(returncode=2, stdout='', stderr='...')` for the standard sync.
  - `lib.lib_emailer.Emailer.send_email` to a mock.
- Call `UvUpdater.manage_sync(...)`.
- Assert:
  - `send_email` was called exactly once.
  - The email body contains the stderr text (or at least the phrase `uv sync failed`).

Also add a test for control-flow:
- Assert that `manage_sync()` raises after sending the email (or returns `ok=False` and that `manage_update()` would halt).

### F) How to run tests
From repo root:

```bash
uv run ./run_tests.py -v
```

To run just the uv-updater tests:

```bash
uv run ./run_tests.py -v tests.test_uv_updater
```

## Completion criteria
- A `uv sync` failure triggers **at least one** email attempt to project admins.
- The update run does not silently continue as if nothing happened.
- A unit test covers the failure-email behavior.

## Notes for a future work session
- The log snippet suggests the failure is triggered by a dependency-group naming mismatch (`production` vs `prod`). That issue is separate from the notification bug; fixing it would likely reduce how often this path is hit, but it should not be required for error-email correctness.
