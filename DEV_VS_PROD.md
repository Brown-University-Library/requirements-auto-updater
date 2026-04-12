# Dev vs Production Processing

This document summarizes the code-level differences in how the auto-updater behaves when run on a dev server versus a production server.

## Environment detection

The script infers environment from the machine hostname in `determine_environment_type()`.

- Hostnames starting with `d` or `q` are treated as `staging`
- Hostnames starting with `p` are treated as `production`
- Anything else is treated as `local`

Source:
- `requirements-auto-updater/lib/lib_environment_checker.py:222`
- `requirements-auto-updater/tests/test_environment_checks.py:457`

In practice, a dev server run is handled as a `staging` run, while a production server run is handled as `production`.

## Actual processing differences

### 1. Different dependency groups are synced

The `uv sync` command uses different dependency groups depending on environment:

- `staging` uses `--group staging`
- `production` uses `--group prod`

Source:
- `requirements-auto-updater/lib/lib_uv_updater.py:147`

### 2. Dev/staging runs tests; production skips them

The helper `should_run_tests()` returns `False` only for `production`.

That means:

- On dev/staging, the script runs the target project's tests before any update
- On dev/staging, the script runs the target project's tests again after an update
- On production, both of those test phases are skipped

Source:
- `requirements-auto-updater/lib/lib_call_runtests.py:25`

### 3. Post-update rollback due to failed tests is effectively dev/staging-only

After a substantive update, `manage_update()` runs follow-up tests and rolls back if those tests fail.

Because production skips follow-up tests, this rollback path is only realistically triggered on dev/staging.

Source:
- `requirements-auto-updater/auto_updater.py:166`

### 4. Rollback verification tests are skipped on production

If `uv sync` itself fails inside `UvUpdater.manage_sync()`, the code restores the old `uv.lock` and runs `uv sync --frozen`.

After that:

- Dev/staging reruns tests to verify the environment is healthy again
- Production skips that rollback verification test pass

Source:
- `requirements-auto-updater/lib/lib_uv_updater.py:49`
- `requirements-auto-updater/tests/test_uv_updater.py:154`

## What does not change between dev and production

These parts of processing are the same in both environments:

- the initial project/environment validation steps
- the dry-run classification step
- backup and diff generation for `uv.lock`
- notification email flow
- Django `collectstatic` and restart handling when a Django update is detected
- git add/commit/push handling after a successful substantive update
- final group/permission updates

## Practical summary

The main behavioral distinction is:

- dev server: updates the `staging` dependency group and uses tests as pre- and post-update safety gates
- production server: updates the `prod` dependency group and skips all test execution

So production is the less conservative path. It still performs dry-run analysis, backup, syncing, diffing, notifications, and cleanup, but it does not block or validate the run with test execution.
