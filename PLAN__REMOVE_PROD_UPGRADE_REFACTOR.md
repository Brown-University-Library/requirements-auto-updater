# Plan: Remove Prod Upgrade Refactor

## Prompt

Goal:

Create a plan to implement removal of the `--upgrade` sync on prod -- in the "clean-separation different-workflow" approach outlined in `requirements-auto-updater/IDEA_ASSESSMENT.md`.

Tasks:

- Review the existing code-flow.
- Review the dev/prod analysis at `requirements-auto-updater/DEV_VS_PROD.md`.
- Review `requirements-auto-updater/AGENTS.md` for code-directives to follow.
- Review `requirements-auto-updater/IDEA_ASSESSMENT.md`.
- Create and save an implementation-plan to `requirements-auto-updater/PLAN__REMOVE_PROD_UPGRADE_REFACTOR.md`.
- Add this complete prompt near the top of the plan.
- Don't change any code; just create and save the plan.

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
7. optionally perform Django follow-up work only if the already-committed lockfile implies a Django update relative to the currently-installed environment, or more conservatively, skip that automation until a clear detection strategy is defined
8. do not commit or push from production
9. send only operational/setup failure email if the sync fails
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
- real sync: prefer `uv sync --no-active --locked --group prod`

Rationale:

- `--locked` matches the stated philosophy that production should realize an already-tested `uv.lock`
- this keeps production from resolving a newer dependency set on its own

~~Open decision~~:

- ~~decide whether `--locked` or `--frozen` is the better production flag~~

REVIEWER-DECISION: use `--locked`, because it will raise an error on a mismatch between the lockfile and the pyproject.toml, which I want.

Recommendation:

- use `--locked` for the normal production sync path
- continue using a restore-oriented command for rollback/error recovery paths only if a rollback path remains necessary

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

### 5. Revisit Django follow-up behavior

Current Django follow-up logic is based on a diff in `uv.lock`.

That works for staging because staging mutates `uv.lock`.
It does not naturally fit production if production no longer changes `uv.lock`.

Plan options:

- ~~conservative option: staging keeps Django follow-up automation; production skips this automation entirely for now~~
- more advanced option: introduce a separate production-safe way to detect whether the committed lockfile implies a Django version change in the installed environment

REVIEWER-DECISION: implement the more advanced option. Reason: if django is upgraded, it is essential that collect-static update the admin-files, and that a `touch` is executed to ensure the code-changes are made active.

Recommendation:

- ~~implement the conservative option in this refactor~~

Reason:

- it keeps the refactor focused
- it avoids inventing a second state-comparison system in the same change
- it reduces the chance of subtle production-only behavior regressions

If that conservative choice is taken, document it clearly in the README and in the dev/prod analysis doc.

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

Likely answer:

- if production uses `--locked` and does not mutate `uv.lock`, rollback complexity should be much smaller
- production may only need failure reporting, not lockfile restoration logic

REVIEWER-DECISION: i aggree. if production uses `--locked` and does not mutate `uv.lock`, then production only needs failure logging and email notifications.

## File-level implementation plan

### `requirements-auto-updater/auto_updater.py`

Planned changes:

- extract the shared preflight setup from the environment-specific workflow body
- add separate staging and production workflow helpers
- make staging retain the current dry-run -> backup -> upgrade -> diff -> follow-up path
- make production bypass dry-run classification, `uv.lock` backup/diff, follow-up tests, and git operations
- keep final permissions/group cleanup common
- fix the direct `--group production` rollback bug by routing all group naming through updater helpers or a shared mapping helper

### `requirements-auto-updater/lib/lib_uv_updater.py`

Planned changes:

- replace the current generic `make_sync_command()` usage pattern with explicit command helpers
- preserve dry-run classification for staging only
- add a production-safe locked sync helper
- narrow `manage_sync()` responsibilities, or split it into:
  - upgrade-oriented staging sync behavior
  - locked production sync behavior
- simplify or remove rollback logic that only made sense when `uv.lock` was being changed

### `requirements-auto-updater/lib/lib_call_runtests.py`

Likely no major structural changes.

Possible changes:

- none, if production continues to skip tests
- at most, docstring updates if workflow descriptions become more explicit

### `requirements-auto-updater/lib/lib_django_updater.py`

Likely no immediate code changes unless production Django automation is retained.

REVIEWER-DECISION: we will retain post-update django automation, so redo this part.

If production Django automation is skipped for this refactor:

- no code change may be needed here
- only staging would continue to call it from the top-level workflow

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

## Test plan

Add or update unit tests before or alongside code changes.

### Environment/workflow orchestration tests

In `tests/test_auto_updater.py`, add coverage for:

- staging path still calling dry-run classification
- staging path still calling upgrade sync and diff logic
- production path bypassing dry-run classification
- production path bypassing `uv.lock` backup and compare steps
- production path bypassing git handling
- production path still calling final permissions/group update

### Command-construction tests

In `tests/test_uv_updater.py`, add coverage for:

- staging dry-run command includes `--upgrade`, `--dry-run`, and `--output-format json`
- staging real sync command includes `--upgrade`
- production sync command includes `--locked` and `--group prod`
- rollback/restore command uses the proper dependency-group mapping and never uses `--group production`

### Behavioral tests for production path

Add tests for:

- production locked sync success path
- production locked sync failure path sends the expected failure email
- production path does not invoke rollback verification tests
- production path does not attempt `uv.lock` diff-based downstream actions

### Regression tests

Keep or expand tests that already verify:

- production skips rollback tests
- environment detection maps dev/qa to staging and prod hostnames to production

## Implementation order

1. Add or revise tests that describe the intended workflow split.
2. Refactor command construction in `lib/lib_uv_updater.py` so command intent is explicit.
3. Refactor `auto_updater.py` to separate staging and production workflows.
4. Simplify production failure handling around locked sync semantics.
5. Decide and implement the conservative Django behavior for production.
6. Update docs: `README.md` and `DEV_VS_PROD.md`.
7. Run `uv run ./run_tests.py`.

## Risks to watch

- accidental retention of dry-run upgrade logic on production
- accidental production mutation of `uv.lock`
- accidental production git commit/push behavior
- inconsistent dependency-group naming between `production` and `prod`
- preserving staging behavior while refactoring shared helpers
- hidden assumptions in email content that expect a `uv.lock` diff to exist

## Decisions to make before implementation

These decisions should be resolved before coding starts:

1. Confirm that production should use `--locked` rather than `--frozen` for its normal sync path.
2. Confirm whether production should skip Django follow-up automation for this refactor.
3. Confirm whether production should send any "success" email at all, or only failure/setup emails.
4. Confirm whether any existing operational process depends on production still doing dry-run upgrade detection.

## Recommended implementation stance

Implement this as an explicit workflow split, not as a flag tweak.

That means:

- staging remains the only environment that discovers and commits dependency upgrades
- production becomes a sync-only consumer of the committed `uv.lock`
- command construction is made explicit enough that future regressions are harder to introduce

This approach is larger than a one-line change, but it is the design that best matches the stated safety model.
