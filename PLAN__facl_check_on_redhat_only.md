# PLAN: Skip `getfacl` Check On Local Development

## Goal

Change the preflight flow so the default-ACL check is skipped for local development and still runs for `staging` and `production`, where this environmental validation is relevant.


## First Step Before Implementation

Review `AGENTS.md` and follow its repository directives. That has been done for this task.


## Current State

- `auto_updater.run_preflight_checks()` always calls `lib_environment_checker.check_default_directory_facls(...)` after `determine_group()`.
- `determine_environment_type()` currently returns only `local`, `staging`, or `production`, based on hostname prefixes.
- The ACL checker itself directly shells out to `getfacl`, so local macOS runs will fail before the updater reaches the rest of preflight.


## Recommendation

Add a small environment-type gating helper in `lib/lib_environment_checker.py` and use it in preflight to decide whether the ACL check should run.

Recommended shape:

```python
def should_check_facls(environment_type: str) -> bool:
```

Behavior:

- Return `False` if `environment_type` is anything other than `staging` or `production`.
- Return `True` if `environment_type` is `staging` or `production`.
- Keep `check_default_directory_facls()` focused on ACL validation only; do not bury environment-detection logic inside it.


## Why This Shape

- It keeps the skip decision near preflight orchestration, where the other environment-dependent decisions already live.
- It respects the current meaning of `environment_type`, which is deployment role.
- It cleanly solves the actual problem: local macOS should not try to run `getfacl`.
- It gives tests a narrow seam to patch without needing to mock `getfacl` for local-only scenarios.


## Gating Rule

Use `environment_type` only. `determine_environment_type()` already returns `local`, `staging`, or `production`, and that is enough to decide whether the ACL check should run.

Recommended approach:

1. If `environment_type` is `local`, skip the ACL check.
2. If `environment_type` is `staging` or `production`, run the ACL check.

Why this approach:

- It is the smallest correct change.
- It cleanly excludes macOS local development.
- It avoids introducing OS-detection logic that the feedback says is unnecessary.

Alternative:

- Adding RedHat detection is unnecessary for the stated requirement.


## Proposed Code Changes

### 1. Add a gating helper

File: `lib/lib_environment_checker.py`

Add a helper such as:

```python
def should_check_facls(environment_type: str) -> bool:
```

Implementation outline:

- if `environment_type` is `'staging'` or `'production'`: return `True`
- otherwise: return `False`

This keeps the existing environment-type API intact and makes the gating rule explicit in one place.

This helper should log its decision at `info` level so the skip is visible in updater logs.


### 2. Gate the existing ACL check in preflight

File: `auto_updater.py`

Replace the unconditional call:

```python
lib_environment_checker.check_default_directory_facls(project_path, group, project_email_addresses)
```

with:

```python
if lib_environment_checker.should_check_facls(environment_type):
    lib_environment_checker.check_default_directory_facls(project_path, group, project_email_addresses)
```

This preserves the existing ACL-check implementation and error handling for `staging` and `production` while skipping it on `local`.


### 3. Keep `check_default_directory_facls()` unchanged unless needed

File: `lib/lib_environment_checker.py`

The ACL checker already handles:

- missing `getfacl`
- non-zero return code
- missing expected ACL line

Those behaviors are still correct when the function is called only for `staging` and `production`, so no functional rewrite is needed unless log wording should mention the local-development skip.


## Tests To Add Or Update

### 1. New helper tests

File: `tests/test_environment_checks.py`

Add focused tests for `should_check_facls()`:

- returns `False` for `local`
- returns `True` for `staging`
- returns `True` for `production`
- returns `False` for any unexpected value, to keep the helper conservative

Testing approach:

- direct unit tests, no filesystem patching needed


### 2. Preflight orchestration tests

File: `tests/test_auto_updater.py`

Update common patches to include:

```python
patch('auto_updater.lib_environment_checker.should_check_facls', return_value=True)
```

Add focused orchestration coverage for:

- ACL check is called when helper returns `True`
- ACL check is not called when helper returns `False`


### 3. Existing ACL function tests

File: `tests/test_environment_checks.py`

Keep the existing `check_default_directory_facls()` tests. They still cover the validation logic itself and should not need semantic changes.


## Expected Outcome

- Local macOS development no longer attempts to run `getfacl`.
- `staging` and `production` still enforce the ACL preflight check.
- The skip rule is captured in one explicit helper instead of being embedded implicitly in preflight.


## Validation

After implementation, run:

```bash
uv run ./run_tests.py
```

If more targeted execution is needed, run the environment-check and auto-updater test modules first.
