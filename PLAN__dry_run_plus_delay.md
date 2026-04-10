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

This matters because any dry-run / temp-copy implementation should be written around the target project, not around the updater repo.

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

### Practical implementation seam options

There are at least three plausible implementation strategies. If a later session needs to choose quickly, use this order of preference:

1. ~~Preferred: dry-run preflight plus isolated temp-copy prospective diff~~
   - ~~stable and explicit~~
   - ~~avoids mutating the real target repo~~
   - ~~does not depend entirely on parsing human-oriented dry-run text~~

2. Acceptable if uv output proves sufficiently stable: dry-run preflight plus parsing dry-run plan text
   - simpler
   - but potentially more brittle if uv output wording changes

3. ~~Fallback only if needed: isolated temp-copy real lock update without relying on dry-run output semantics~~
   - ~~still avoids mutating the real target repo~~
   - ~~slightly heavier, but likely robust~~

DEVELOPER RESPONSE: use option-2.

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

Prospective lock-only planning candidate:

```bash
uv lock --upgrade --dry-run
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
- If an implementation session chooses to use a temp directory to compute a prospective diff, tests should exercise that logic with local temp files and mocked uv subprocess responses where practical.

### Open implementation questions to resolve when coding

These do not block the plan, but a future session should answer them deliberately instead of by accident:

1. Does current `uv lock --upgrade --dry-run` output provide enough stable detail to classify "metadata-only" vs "substantive" without a temp-copy fallback?
    - DEVELOPER RESPONSE: let's make this work.
2. Should the new classifier live in `lib/lib_uv_updater.py`, or is it cleaner to create a small dedicated helper module?
    - DEVELOPER RESPONSE: let's create a small dedicated helper module.
3. Should metadata-only skips be logged only, or should they also generate a lightweight informational email?
    - DEVELOPER RESPONSE: let's log only for now.
4. Should the actual post-sync `compare_uv_lock_files()` check remain in place as a defensive verification, even after the new preflight gate is added?
    - DEVELOPER RESPONSE: that logic may still be useful -- make your own determination.
5. Should the classifier ignore only `exclude-newer`, or should it also ignore future uv-generated metadata-only fields if they appear?
    - DEVELOPER RESPONSE: i think ignoring only exclude-newer is the safe way to start.

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
2. A **prospective diff classifier** to determine whether the pending change is substantive or only lockfile metadata churn.

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

### 2. Add a prospective-update classifier before the real sync

The main design requirement is to decide whether to proceed **without touching the real repo**.

Because the dry-run output is documented as human-readable, but not clearly documented as a stable machine interface, the safer design is:

- use `uv sync --upgrade --dry-run` as the first gate
- if it reports no pending change, stop immediately
- if it reports pending change, compute a **prospective lockfile diff in isolation**

Recommended approach for the second step:

- create a temporary working directory
- copy in the minimum files needed for lock resolution:
  - `pyproject.toml`
  - current `uv.lock`
  - any other uv config file only if this repo already depends on one
- run a lock-only resolution there, preferably:

```bash
uv lock --upgrade --dry-run
```

If `uv lock --dry-run` does not provide enough detail in practice, the fallback design is:

- create the temp copy
- run real `uv lock --upgrade` in the temp copy only
- diff the temp-copy `uv.lock` against the original repo `uv.lock`

This keeps the target repo untouched while still producing the exact prospective diff needed for classification.

### 3. Add a uv.lock diff classifier that distinguishes substantive vs metadata-only changes

Add a focused helper in `lib/lib_uv_updater.py` or a new small helper module.

Suggested responsibility:

- inspect a unified diff of `uv.lock`
- return whether the diff is:
  - substantive
  - metadata-only
  - specifically limited to `[options] exclude-newer` / `exclude-newer-span`

For the first pass, the classifier can be deliberately narrow:

- treat changes as **ignorable** only when the diff is confined to the `[options]` block lines:
  - `exclude-newer = "..."`
  - `exclude-newer-span = "..."`
- treat everything else as substantive

That conservative rule is preferable to a broader heuristic. It avoids suppressing real dependency changes by accident.

Suggested shape:

- `classify_uv_lock_diff(diff_text: str) -> dict[str, bool | str]`
- or a small `TypedDict` / dataclass with flags such as:
  - `has_changes`
  - `is_substantive`
  - `is_exclude_newer_only`

### 4. Refactor `auto_updater.manage_update()` to gate the real update

Replace the current sequence:

- backup `uv.lock`
- real `uv sync --upgrade`
- compare `uv.lock`

with a gated sequence:

1. run dry-run preflight
2. if dry run says "no pending changes", log and exit update path
3. if dry run says "pending changes", compute prospective diff
4. classify the prospective diff
5. if classifier says "exclude-newer only", log and exit update path
6. only then:
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

- if the classifier says the prospective diff is metadata-only, the code should never reach Django update handling
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
- diff classifier returns substantive for normal package version bumps
- diff classifier returns metadata-only for this exact pattern:

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

- diff classifier returns substantive if any package block also changes

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
- A prospective diff consisting only of `[options] exclude-newer` / `exclude-newer-span` changes does not trigger:
  - real `uv.lock` rewrite
  - `.venv` update
  - follow-up tests
  - git add / commit / push
  - normal update email
- A substantive dependency change still triggers the current update, rollback, test, git, and email workflow.
- Django-specific follow-up logic still runs only when Django's package version actually changes.
- The README reflects the new decision flow.

## Notes for implementation

- Keep the classifier conservative. It is safer to let an uncertain diff count as substantive than to suppress a real dependency update.
- Prefer structured return values over ad hoc tuples for any new dry-run/planning helpers.
- Keep the real mutation path as small a delta from current behavior as possible.
- Follow `AGENTS.md`: Python 3.12 typing, `uv` commands for execution, focused tests, minimal correct change.
