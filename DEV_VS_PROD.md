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

### 1. Different dependency groups and sync semantics are used

The `uv sync` command now uses different dependency groups and different sync modes depending on environment:

- `staging` uses upgrade discovery and real upgrade syncs:
  - `uv sync --no-active --upgrade --group staging --dry-run --output-format json`
  - `uv sync --no-active --upgrade --group staging`
- `production` skips upgrade discovery and realizes the committed lockfile:
  - `uv sync --no-active --locked --group prod`

Source:
- `requirements-auto-updater/lib/lib_uv_updater.py`

### 2. Dev/staging runs tests; production skips them

The helper `should_run_tests()` returns `False` only for `production`.

That means:

- On dev/staging, the script runs the target project's tests before any update
- On dev/staging, the script runs the target project's tests again after an update
- On production, both of those test phases are skipped

Source:
- `requirements-auto-updater/lib/lib_call_runtests.py:25`

### 3. Only staging mutates and diffs `uv.lock`

Staging still backs up `uv.lock`, upgrades dependencies, and diffs the resulting lockfile.

Production no longer:

- runs upgrade dry-run classification
- backs up `uv.lock`
- mutates `uv.lock`
- diffs `uv.lock`
- commits or pushes git changes

Source:
- `requirements-auto-updater/auto_updater.py`

### 4. Rollback due to failed follow-up tests is staging-only

After a substantive staging update, `manage_update()` still runs follow-up tests and rolls back if those tests fail.

That rollback restores the old `uv.lock`, runs `uv sync --frozen --group staging`, and reruns tests to confirm the environment is healthy again.

Production no longer participates in that rollback path because it no longer upgrades or diffs `uv.lock`.

Source:
- `requirements-auto-updater/auto_updater.py`
- `requirements-auto-updater/lib/lib_uv_updater.py`

### 5. Django follow-up detection differs

Staging still decides whether Django follow-up work is required by inspecting the `uv.lock` diff.

Production now decides whether Django follow-up work is required by comparing the installed Django version before and after the locked sync.

This keeps `collectstatic` and restart handling available on production without making production behave like an upgrade-discovery environment.

Source:
- `requirements-auto-updater/auto_updater.py`
- `requirements-auto-updater/lib/lib_django_updater.py`

## What still does not change between dev and production

These parts of processing are still the same in both environments:

- the initial project/environment validation steps
- final group/permission updates
- Django operational follow-up when a Django change has been activated
- setup-problem email notifications when a sync command itself fails

## Practical summary

The main behavioral distinction is:

- dev/staging server: discovers upgrades, mutates `uv.lock`, tests the result, and commits/pushes safe lockfile changes
- production server: consumes the committed `uv.lock` with `--locked`, skips all test execution, and does not perform git work

So production is now a lockfile-realization path rather than an upgrade-discovery path.
