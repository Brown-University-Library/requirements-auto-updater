# Summary

## Original prompt

```text
- review `requirements-auto-updater/IDEA_ASSESSMENT.md` for the original idea, for background context.

- review `requirements-auto-updater/AGENTS.md` for coding directives to follow.

- most important: review `requirements-auto-updater/PLAN__REMOVE_PROD_UPGRADE_REFACTOR.md` -- this is what we'll now be implementing.

- When finished, save a summary to `requirements-auto-updater/SUMMARY.md`, and add this complete prompt near the top of that.

- ok; implement the plan! thx!
```

## What changed

- Split `manage_update()` into a shared preflight section plus separate staging and production workflows in `auto_updater.py`.
- Kept staging as the upgrade-discovery path: dry-run classification, `uv.lock` backup, real `--upgrade` sync, diff handling, follow-up tests, rollback, git, and diff email.
- Changed production into a lockfile-realization path: no dry-run upgrade discovery, no `uv.lock` backup/diff, no git work, and a real `uv sync --no-active --locked --group prod`.
- Replaced the generic sync-command builder in `lib/lib_uv_updater.py` with explicit helpers for upgrade dry-run, upgrade sync, locked sync, and restore sync.
- Centralized dependency-group mapping so rollback/restore commands use `prod` rather than the old incorrect `production` group name.
- Added production-safe Django follow-up detection in `lib/lib_django_updater.py` by comparing installed package metadata before and after the locked sync.

## Tests

- Updated `tests/test_auto_updater.py` to cover the new staging and production workflow split.
- Updated `tests/test_uv_updater.py` to cover the new command builders and separate staging/production sync failure behavior.
- Updated `tests/test_django_updater.py` to cover installed-version detection and package-version-change checks.
- Ran `uv run ./run_tests.py -v` successfully.

## Docs

- Updated `README.md` to describe staging as the only upgrade-discovery environment and production as a `--locked` lockfile-consumer.
- Updated `DEV_VS_PROD.md` to reflect the new workflow separation and production Django follow-up detection.
