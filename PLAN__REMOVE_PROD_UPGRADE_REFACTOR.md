# Plan: Remove Prod Upgrade Refactor

## Goal of the refactor

Change the script so that:

- `staging` remains the environment that discovers dependency upgrades
- `staging` remains the environment that mutates `uv.lock`
- `staging` remains the environment that runs tests before and after upgrades
- `production` stops acting as an upgrade-discovery environment
- `production` becomes a lockfile-consumer environment that syncs `.venv` to the already-committed `uv.lock`

This is the "clean-separation different-workflow" approach described in `requirements-auto-updater/IDEA_ASSESSMENT.md`.


## Current flow to refactor

The current code assumes one update workflow for all environments:

1. run initial environment checks
2. run initial tests unless `production`
3. run `uv sync --upgrade --dry-run --output-format json`
4. classify dry-run output
5. if substantive, back up `uv.lock`
6. run real `uv sync --upgrade`
7. diff `uv.lock`
8. handle Django follow-up work
9. run follow-up tests unless `production`
10. on success, commit/push/email
11. on failure, roll back and email

That structure currently lives primarily in:

- `requirements-auto-updater/auto_updater.py`
- `requirements-auto-updater/lib/lib_uv_updater.py`
- `requirements-auto-updater/lib/lib_call_runtests.py`

## Desired future flow

### Staging flow

Keep the existing staging behavior in principle:

1. run environment checks
2. run initial tests
3. run upgrade dry-run
4. if no substantive change, stop
5. if substantive change, back up `uv.lock`
6. run real upgrade sync
7. diff `uv.lock`
8. run follow-up work and tests
9. commit/push/email on success
10. roll back and email on failure

### Production flow

Make production a distinct path:

1. run environment checks
2. skip tests, as now
3. do not run upgrade discovery
4. do not classify upstream upgrade availability
5. do not mutate `uv.lock`
6. run a lockfile-realization sync only
7. retain Django follow-up automation through a production-safe detection path
8. do not commit or push from production
9. send operational/setup failure email if the sync fails
10. still update group/permissions at the end

The most important architectural change is:

- `staging` remains an "update workflow"
- `production` becomes a "deployment/sync workflow"

## Planning assumptions

- Keep the current hostname-based environment detection unchanged.
- Keep `production` test skipping unchanged unless separately revisited.
- Keep `staging` as the environment that mutates `uv.lock`.
- Prefer the smallest refactor that creates a genuinely separate production workflow, rather than adding more conditionals into the existing unified flow.
- Preserve current email behavior where practical, but avoid pretending production discovered an upgrade when it did not.

## Recommended command semantics

For staging:

- dry-run: `uv sync --no-active --upgrade --group staging --dry-run --output-format json`
- real sync: `uv sync --no-active --upgrade --group staging`

For production:

- no upgrade dry-run path
- real sync: `uv sync --no-active --locked --group prod`

Rationale:

- `--locked` matches the stated philosophy that production should realize an already-tested `uv.lock`
- `--locked` also fails if `pyproject.toml` and `uv.lock` are inconsistent, which is desired here
- this keeps production from resolving a newer dependency set on its own

Decision:

- use `--locked` for the normal production sync path

Recommendation:

- use `--locked` for the normal production sync path
- keep any restore-oriented command limited to staging rollback/error recovery paths only if such paths remain necessary after refactoring

## Refactor shape

### 1. Separate workflow decision earlier in `manage_update()`

Refactor `manage_update()` so it branches by workflow after the shared environment checks:

- shared preflight section remains common
- staging uses an upgrade-oriented path
- production uses a locked-sync path

This should reduce ambiguity and make the two workflows obvious in the top-level orchestration.

Preferred structure:

- `manage_update()` remains the top-level orchestrator
- add small top-level helpers such as:
  - `run_staging_update_workflow(...)`
  - `run_production_sync_workflow(...)`

This matches the repository guidance to keep orchestration in top-level helpers and avoid nested functions.

### 2. Stop using one generic sync command builder for incompatible jobs

`lib/lib_uv_updater.py` currently conflates:

- upgrade sync
- frozen rollback sync
- dry-run upgrade discovery

Plan to split that into explicit command builders or explicit helper methods, for example:

- `make_upgrade_dry_run_command(...)`
- `make_upgrade_sync_command(...)`
- `make_locked_sync_command(...)`
- `make_restore_sync_command(...)`

That will make the intent of each call site much clearer and remove the current "one function plus `sync_type` string" coupling.

### 3. Remove upgrade discovery from production

Production should not call the dry-run classifier path at all.

This means:

- `inspect_pending_sync()` stays relevant for staging
- production should bypass `inspect_pending_sync()`
- production should not enter diff/commit logic driven by dry-run classification

This is the core behavioral change that makes the workflow separation real.

### 4. Remove `uv.lock` mutation expectations from production

The current update flow assumes:

- back up `uv.lock`
- run sync
- compare new `uv.lock` to backup
- use the diff for downstream email and git work

That should remain staging-only.

For production:

- do not back up `uv.lock` as part of the normal path
- do not compare `uv.lock` files in the normal path
- do not trigger git commit/push behavior

This should significantly simplify the production path.

### 5. Retain Django follow-up behavior on production

Current Django follow-up logic is based on a diff in `uv.lock`.

That works for staging because staging mutates `uv.lock`.
It does not naturally fit production if production no longer changes `uv.lock`.

Plan direction:

- retain post-update Django automation on production
- introduce a production-safe way to determine whether Django follow-up work is required without relying on a newly-mutated `uv.lock` diff

Reason:

- if Django changes are activated via dependency updates, production still needs `collectstatic` and the reload `touch`
- those steps are operationally required even when production is only consuming a committed lockfile

Implementation note:

- keep this detection logic explicit and isolated so it does not blur the clean workflow split

### 6. Clean up rollback semantics

There is already a production-related inconsistency in rollback handling:

- `auto_updater.py` currently builds `uv sync --frozen --group production`
- elsewhere the dependency group is mapped to `prod`

As part of the refactor:

- centralize dependency-group resolution
- ensure all commands use the same group mapping
- avoid any direct use of `environment_type` as a dependency-group name

Additionally:

- decide whether production still needs rollback behavior at all once it becomes a locked-sync path

Decision:

- if production uses `--locked` and does not mutate `uv.lock`, production only needs failure logging and email notifications

## File-level implementation plan

### `requirements-auto-updater/auto_updater.py`

Planned changes:

- extract the shared preflight setup from the environment-specific workflow body
- add separate staging and production workflow helpers
- make staging retain the current dry-run -> backup -> upgrade -> diff -> follow-up path
- make production bypass dry-run classification, `uv.lock` backup/diff, follow-up tests, and git operations
- make production retain any required Django follow-up and restart handling via a production-safe detection path
- keep final permissions/group cleanup common
- fix the direct `--group production` rollback bug by routing all group naming through updater helpers or a shared mapping helper

### `requirements-auto-updater/lib/lib_uv_updater.py`

Planned changes:

- replace the current generic `make_sync_command()` usage pattern with explicit command helpers
- preserve dry-run classification for staging only
- add a production-safe locked sync helper
- add a production-safe Django-change detection helper, or another explicit helper that enables Django follow-up without relying on a staging-style diff
- narrow `manage_sync()` responsibilities, or split it into:
  - upgrade-oriented staging sync behavior
  - locked production sync behavior
- simplify or remove production rollback logic that only made sense when `uv.lock` was being changed

### `requirements-auto-updater/lib/lib_call_runtests.py`

Likely no major structural changes.

Possible changes:

- none, if production continues to skip tests
- at most, docstring updates if workflow descriptions become more explicit

### `requirements-auto-updater/lib/lib_django_updater.py`

Planned changes:

- review whether the current API, which keys off a `uv.lock` diff, is sufficient once production no longer mutates `uv.lock`
- if not sufficient, add a focused helper for production-safe Django change detection
- keep the existing `collectstatic` execution and restart-touch responsibilities here or in a closely related helper module, rather than spreading them into `auto_updater.py`

### `requirements-auto-updater/README.md`

Planned doc updates after code change:

- revise the flow section so production is described as lockfile realization, not upgrade discovery
- clarify that staging is the only environment that discovers and commits dependency upgrades
- clarify the exact production sync command behavior

### `requirements-auto-updater/DEV_VS_PROD.md`

Planned doc updates after code change:

- update the "what differs" section
- remove references to production dry-run upgrade classification if that no longer happens
- note that production no longer mutates `uv.lock`
- note that production still performs Django follow-up automation when required

## Test plan

Add or update unit tests before or alongside code changes.

### Environment/workflow orchestration tests

In `tests/test_auto_updater.py`, add coverage for:

- staging path still calling dry-run classification
- staging path still calling upgrade sync and diff logic
- production path bypassing dry-run classification
- production path bypassing `uv.lock` backup and compare steps
- production path bypassing git handling
- production path retaining Django follow-up decision-making when appropriate
- production path still calling final permissions/group update

### Command-construction tests

In `tests/test_uv_updater.py`, add coverage for:

- staging dry-run command includes `--upgrade`, `--dry-run`, and `--output-format json`
- staging real sync command includes `--upgrade`
- production sync command includes `--locked` and `--group prod`
- rollback/restore command uses the proper dependency-group mapping and never uses `--group production`
- any production Django-detection helper uses production-appropriate inputs rather than a staging-only `uv.lock` diff assumption

### Behavioral tests for production path

Add tests for:

- production locked sync success path
- production locked sync failure path sends the expected failure email
- production path does not invoke rollback verification tests
- production path does not attempt `uv.lock` diff-based downstream actions
- production path still runs Django follow-up automation when the new detection logic says it should

### Regression tests

Keep or expand tests that already verify:

- production skips rollback tests
- environment detection maps dev/qa to staging and prod hostnames to production

## Implementation order

1. Add or revise tests that describe the intended workflow split.
2. Refactor command construction in `lib/lib_uv_updater.py` so command intent is explicit.
3. Refactor `auto_updater.py` to separate staging and production workflows.
4. Simplify production failure handling around locked sync semantics.
5. Implement the production-safe Django follow-up detection and keep the required Django automation path.
6. Update docs: `README.md` and `DEV_VS_PROD.md`.
7. Run `uv run ./run_tests.py`.

## Risks to watch

- accidental retention of dry-run upgrade logic on production
- accidental production mutation of `uv.lock`
- accidental production git commit/push behavior
- inconsistent dependency-group naming between `production` and `prod`
- preserving staging behavior while refactoring shared helpers
- hidden assumptions in email content that expect a `uv.lock` diff to exist
- designing Django follow-up detection for production without reintroducing upgrade-discovery behavior there

## Decisions to make before implementation

Pre-implementation instructions:

- review `requirements-auto-updater/AGENTS.md` immediately before making any code changes
- follow the repository workflow there, including updating tests and running `uv run ./run_tests.py`

Remaining decisions:

1. Confirm whether production should send any "success" email at all, or only failure/setup emails.
2. Confirm whether any existing operational process depends on production still doing dry-run upgrade detection.
3. Confirm the exact production-safe source of truth for deciding that Django follow-up automation is required.

## Recommended implementation stance

Implement this as an explicit workflow split, not as a flag tweak.

That means:

- staging remains the only environment that discovers and commits dependency upgrades
- production becomes a sync-only consumer of the committed `uv.lock`
- command construction is made explicit enough that future regressions are harder to introduce

This approach is larger than a one-line change, but it is the design that best matches the stated safety model.

---
