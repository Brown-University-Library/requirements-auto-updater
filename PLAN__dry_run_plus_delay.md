# Plan: dry-run gate plus exclude-newer delay

Goal: change the updater so it decides whether to proceed **before** mutating the target repo's `uv.lock` file or `.venv`, while also ignoring lockfile-only churn caused by different `exclude-newer` values such as:

```toml
[tool.uv]
exclude-newer = "1 week"
```

The intended end-state is:

- If `uv` reports no pending upgrade, do nothing.
- If `uv` reports only the rolling `[options] exclude-newer` timestamp/span change in `uv.lock`, do nothing.
- Only if there is a **substantive dependency change** should the updater run the real upgrade, update `.venv`, run follow-up steps, and perform git operations.

## Relevant current behavior

The current update path is orchestrated in `auto_updater.py`:

- `manage_update()` backs up `uv.lock`
- then immediately runs `uv sync --upgrade --group ...`
- then compares `uv.lock` vs `uv.lock.bak`
- then treats any diff as "changes happened" and proceeds to tests, optional `collectstatic`, email, and git work

Relevant files reviewed:

- `auto_updater.py`
- `lib/lib_uv_updater.py`
- `lib/lib_call_runtests.py`
- `lib/lib_django_updater.py`
- `lib/lib_git_handler.py`
- `lib/lib_emailer.py`
- `tests/test_uv_updater.py`
- `tests/test_django_updater.py`
- `README.md`

Today, the decision boundary is effectively:

- `compare_result['changes'] is True` => proceed
- `compare_result['changes'] is False` => stop

That is too broad for the new requirement, because a rolling `exclude-newer` timestamp change will still produce a diff even when no package versions changed.

## Current Astral uv documentation

Current Astral docs indicate:

- `uv sync --dry-run` performs a dry run without writing the lockfile or modifying the project environment, and reports resulting changes.
- `uv lock --dry-run` performs dependency resolution and reports changes without writing the lockfile.
- `uv lock --check` is not sufficient for this use-case, because it only checks whether the lockfile matches project metadata; it does not answer whether newer allowed package versions are available.

Implication for implementation:

- A dry-run-based preflight is now supported by uv.
- However, the docs I reviewed do not document a machine-readable "updates available" exit code for this workflow, so the implementation should avoid relying on undocumented exit-status semantics alone.

## Session context for future implementation

This section is intended to save time if the implementation happens in a later session with less context loaded.

### Repository and runtime assumptions

- Repository root contains:
  - `auto_updater.py`
  - `run_tests.py`
  - `pyproject.toml`
  - `uv.lock`
  - `ruff.toml`
  - `lib/`
  - `tests/`
- The repo-level instructions in `AGENTS.md` say:
  - primary language is Python
  - target runtime is Python 3.12
  - execution tool is `uv`
  - tests should be run via `uv run ./run_tests.py`
- Current branch created for this planning work: `dry-run-plus-delay`

### Current target-project behavior assumptions in this codebase

The updater is not updating itself; it updates a separate target project passed to `auto_updater.py`.

That target project is assumed to contain, at minimum:

- `pyproject.toml`
- `uv.lock`
- `run_tests.py`
- possibly `manage.py` for Django projects
- a `.venv` managed by uv in the project directory

This matters because the dry-run-based implementation should be written around the target project, not around the updater repo.

### Existing environment-group mapping

In `lib/lib_uv_updater.py`, `make_sync_command()` currently maps:

- `local` -> `--group local`
- `staging` -> `--group staging`
- `production` -> `--group prod`

That mapping is easy to miss, and future implementation should preserve it consistently for:

- dry-run preflight
- prospective lockfile planning
- real sync
- rollback sync

### Existing test policy already present in the repo

`lib/lib_call_runtests.py` already has:

- `should_run_tests(environment_type: str) -> bool`

Current behavior:

- returns `False` for `production`
- used by `run_initial_tests()`
- used by `run_followup_tests()`
- also used in rollback logic inside `UvUpdater.manage_sync()`

This is relevant because a future session should avoid reinventing test policy helpers unless the new work truly needs a separate planning/decision helper.

### Existing decision boundary that will be replaced

Current decision-making in `auto_updater.manage_update()` is:

1. `backup_uv_lock()`
2. `manage_sync()` with real `uv sync --upgrade`
3. `compare_uv_lock_files()`
4. `if compare_result['changes'] is True: proceed`

This means the current code determines "should update" only after the real update attempt has already occurred.

Any future implementation should treat that as the main architectural seam to refactor.

### Why the new `[tool.uv] exclude-newer = "1 week"` setting is special

The planned target-project setting is:

```toml
[tool.uv]
exclude-newer = "1 week"
```

(The specific exclude-newer time-period may represent days instead.) The key nuance is that uv writes a concrete timestamp into `uv.lock`, not the literal `"1 week"` string. That means even if package versions are unchanged, the lockfile can still change over time in the `[options]` section because the moving cutoff date advances.

This produces a diff like:

```diff
--- /opt/local/django_projects/pdf_checker_stuff/uv.lock.bak
+++ /opt/local/django_projects/pdf_checker_stuff/pdf_checker_project/uv.lock
@@ -3,7 +3,7 @@
 requires-python = "==3.12.*"

 [options]
-exclude-newer = "2026-04-02T06:00:07.392918043Z"
+exclude-newer = "2026-04-03T06:00:06.511210658Z"
 exclude-newer-span = "P1W"
```

The implementation should explicitly treat this as metadata churn, not as an actual dependency update signal.

### Conservative classification rule to preserve correctness

If implementation happens later and there is uncertainty about the exact uv diff format, keep the rule conservative:

- Ignore only diffs confined to:
  - `[options]`
  - `exclude-newer = "..."`
  - `exclude-newer-span = "..."`
- Treat any other added/removed line as substantive unless proven otherwise

This is the safest first release because false positives are operationally annoying, but false negatives could suppress real dependency updates.

### Chosen implementation approach

Use this implementation strategy:

1. Run `uv sync --no-active --upgrade --group <group> --dry-run`.
2. Parse the dry-run output.
3. Decide from that output whether the update is:
   - no-op
   - `exclude-newer`-only metadata churn
   - substantive dependency change
4. Only if the dry-run output indicates a substantive dependency change should the code proceed to the existing real-update flow.

Reason for choosing this approach:

- it keeps the implementation smaller
- it avoids mutating the target repo before the decision is made
- it aligns with the current goal of making `uv` dry-run output the new decision gate

Tradeoff:

- this approach depends on the stability of uv's human-readable dry-run output
- the implementation should therefore keep parsing logic narrow, explicit, and well tested

### Known downstream effects that must remain gated

A future implementation session should remember that the "should update?" decision does not only control `uv.lock`.

Once the code crosses the current `compare_result['changes']` boundary, it may also trigger:

- `.venv` mutation
- post-update tests
- Django `collectstatic`
- `touch ./config/tmp/restart.txt`
- git pull/add/commit/push in the target repo
- email notifications

That is why the preflight gate must happen before the existing "act on differences" block, not inside it.

### Suggested command examples for a future implementation session

These are examples to validate behavior manually when coding later. They are not yet adopted by repo code.

Dry-run preflight candidate:

```bash
uv sync --no-active --upgrade --group staging --dry-run
```

Real sync currently used by repo logic:

```bash
uv sync --no-active --upgrade --group staging
```

Rollback sync currently used by repo logic:

```bash
uv sync --frozen --group staging
```

### Files most likely to require edits during implementation

Primary:

- `auto_updater.py`
- `lib/lib_uv_updater.py`
- `tests/test_uv_updater.py`

Possible but secondary:

- `lib/lib_django_updater.py`
- `lib/lib_emailer.py`
- `README.md`

Likely unnecessary unless design expands:

- `lib/lib_call_runtests.py`
- `lib/lib_git_handler.py`

### Testing notes for a future session

- The updater repo’s own tests should be run with:

```bash
uv run ./run_tests.py
```

- Because the feature is mostly orchestration and diff classification, unit tests with mocked `subprocess.run()` should cover most of the work.
- Avoid depending on live package-index responses in unit tests.

### Resolved implementation decisions

These decisions have already been made and should be treated as part of the plan:

1. Use the dry-run-output parsing approach.
   - Do not use the temp-copy prospective-diff approach for the first implementation.

2. Put the new parsing/classification code in a small dedicated helper module.
   - Do not keep this logic embedded directly inside `auto_updater.py`.

3. For metadata-only skips, log only.
   - Do not send a lightweight informational email in the first implementation.

4. Ignore only `exclude-newer` metadata churn at first.
   - Do not generalize to other uv-generated metadata-only fields yet.

### Remaining judgment call during coding

One design question remains open enough to decide during implementation:

1. Whether to keep the existing post-sync `compare_uv_lock_files()` check as a defensive verification after the new dry-run gate is added.

Current recommendation:

- keep it, unless the implementation becomes noticeably more complex because of it
- the dry-run gate should become the main decision point
- the post-sync compare can still serve as a defensive confirmation of what actually changed

## Problems to solve

1. The updater currently mutates the target repo before it knows whether the update is meaningful.

2. The updater currently treats every `uv.lock` diff as substantive.

3. With `[tool.uv] exclude-newer = "1 week"`, `uv.lock` will gain a moving timestamp under `[options]`, which creates a diff even when no package versions changed.

4. If that metadata-only diff is allowed through the current workflow, it can trigger:

- an unnecessary real `uv.lock` rewrite
- an unnecessary `.venv` update attempt
- unnecessary tests / `collectstatic`
- unnecessary git add / commit / push
- noisy notification email

## Proposed implementation shape

Use a two-stage decision path:

1. A **dry-run preflight** to determine whether `uv` sees any pending upgrade at all.
2. A **dry-run output classifier** to determine whether the pending change is substantive or only `exclude-newer` metadata churn.

Only after both stages say "yes" should the updater perform the real `uv sync --upgrade`.

## Proposed changes

### 1. Add a dry-run preflight helper in `lib/lib_uv_updater.py`

Add a helper responsible for building and running a command equivalent to:

```bash
uv sync --no-active --upgrade --group <group> --dry-run
```

Suggested responsibilities:

- build the dry-run command from the same environment/group mapping already used by `make_sync_command()`
- execute it in the target project directory
- capture stdout/stderr
- return a structured result, not a raw tuple

Suggested shape:

- keep `make_sync_command()` for the real run
- add either:
  - `make_dry_run_sync_command(...)`
  - or extend command creation so `sync_type` and `dry_run` are explicit flags

The dry-run helper should not decide substantive vs metadata-only; it should only answer:

- did the dry run succeed?
- did uv report any pending change?
- what text should be logged or inspected later?

### 2. Add a dry-run output classifier before the real sync

The main design requirement is to decide whether to proceed **without touching the real repo**.

The chosen approach is:

- run `uv sync --upgrade --dry-run`
- inspect the dry-run output text
- stop immediately if the output indicates no pending changes
- stop immediately if the output indicates only `exclude-newer`-driven lockfile churn
- proceed only if the output indicates a substantive dependency change

Implementation notes:

- put this parsing/classification code in a new small helper module
- keep the parser narrow and purpose-built
- do not try to build a general uv output parser in the first pass

Suggested responsibility for the helper:

- inspect dry-run stdout/stderr
- detect whether uv is reporting any update at all
- detect whether the only reported lockfile change is the rolling `exclude-newer` / `exclude-newer-span` metadata
- return a structured classification result

Conservative rule:

- ignore only clearly identified `exclude-newer` metadata churn
- treat anything else as substantive unless the parser can confidently classify it as no-op

Suggested shape:

- `classify_dry_run_output(output_text: str) -> dict[str, bool | str]`
- or a small `TypedDict` / dataclass with flags such as:
  - `has_pending_change`
  - `is_substantive`
  - `is_exclude_newer_only`
  - `summary`

### 4. Refactor `auto_updater.manage_update()` to gate the real update

Replace the current sequence:

- backup `uv.lock`
- real `uv sync --upgrade`
- compare `uv.lock`

with a gated sequence:

1. run dry-run preflight
2. classify the dry-run output
3. if classifier says "no pending changes", log and exit update path
4. if classifier says "exclude-newer only", log and exit update path
5. only then:
   - back up `uv.lock`
   - run real `uv sync --upgrade`
   - compare actual `uv.lock` vs backup
   - continue with existing follow-up tests / django / git / email flow

This preserves the current rollback behavior for real updates while preventing mutation for no-op or metadata-only cases.

### 5. Keep the existing post-update safety flow for substantive updates

The following should stay in place for real updates:

- rollback on failed `uv sync`
- rollback on failed post-update tests
- `collectstatic` only when Django actually changed
- git add / commit / push only after a substantive real update
- notification email containing the substantive diff

The only change to this area should be that it is reached less often, because metadata-only cases stop earlier.

### 6. Keep Django-specific logic tied to substantive package diffs

`lib/lib_django_updater.py` already parses package-block version changes in `uv.lock`.

That logic should remain downstream of the new substantive gate:

- if the classifier says the dry-run result is metadata-only, the code should never reach Django update handling
- if a substantive update does proceed, Django detection can continue to operate on the actual post-sync diff as it does now

### 7. Adjust logging and email semantics

Add explicit log messages for the new skip reasons:

- dry run found no pending upgrade
- dry run found only `exclude-newer` metadata churn
- substantive update detected; proceeding with real sync

Email behavior should remain unchanged for real updates, but metadata-only skips should not trigger the normal "update happened" email.

No new email is required for the initial implementation unless operational visibility is needed. Logging alone is likely sufficient.

### 8. Update README flow documentation

After implementation, update `README.md` so it no longer describes the updater as always discovering changes by mutating the repo first.

The README should instead describe:

- dry-run preflight
- metadata-only `exclude-newer` diffs being ignored
- real sync occurring only for substantive dependency changes

## Test plan

Add focused unit tests before changing behavior.

### `tests/test_uv_updater.py`

Add tests for the new preflight and classification helpers:

- dry-run helper returns success and indicates no pending changes
- dry-run helper returns success and indicates pending changes
- dry-run helper failure path preserves stderr details
- dry-run output classifier returns substantive for normal dependency-update output
- dry-run output classifier returns metadata-only for output that reflects this exact `uv.lock` pattern:

```diff
--- a/uv.lock
+++ b/uv.lock
@@ -3,7 +3,7 @@
 requires-python = "==3.12.*"

 [options]
-exclude-newer = "2026-04-02T06:00:07.392918043Z"
+exclude-newer = "2026-04-03T06:00:06.511210658Z"
 exclude-newer-span = "P1W"
```

- dry-run output classifier returns substantive if any package block also changes

### `auto_updater.manage_update()` behavior tests

Add or extend tests to verify orchestration:

- when dry run reports no change:
  - no backup is created
  - no real sync is run
  - no follow-up tests are run
  - no git operations are run

- when dry run reports only `exclude-newer`-metadata change:
  - no backup is created
  - no real sync is run
  - no follow-up tests are run
  - no git operations are run

- when dry run reports substantive change:
  - the existing real-update path runs

### Regression tests for existing behavior

Keep or update tests covering:

- sync failure rollback
- production rollback test skipping
- actual `uv.lock` unified diff generation
- Django version-bump detection

## Acceptance criteria

- The updater uses a dry-run step before any real `uv.lock` or `.venv` mutation.
- A dry run that reports no pending upgrade causes the updater to stop without creating a backup or running a real sync.
- A dry-run result classified as `[options] exclude-newer` / `exclude-newer-span` metadata-only churn does not trigger:
  - real `uv.lock` rewrite
  - `.venv` update
  - follow-up tests
  - git add / commit / push
  - normal update email
- A substantive dependency change still triggers the current update, rollback, test, git, and email workflow.
- Django-specific follow-up logic still runs only when Django's package version actually changes.
- The README reflects the new decision flow.

## Notes for implementation

- Keep the classifier conservative. It is safer to let uncertain dry-run output count as substantive than to suppress a real dependency update.
- Prefer structured return values over ad hoc tuples for any new dry-run/planning helpers.
- Keep the real mutation path as small a delta from current behavior as possible.
- Follow `AGENTS.md`: Python 3.12 typing, `uv` commands for execution, focused tests, minimal correct change.
