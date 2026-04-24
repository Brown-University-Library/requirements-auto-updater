# PLAN: Run `getfacl` Check Only On RedHat

## Goal

Change the preflight flow so the default-ACL check runs only on RedHat hosts and is skipped for local development, where macOS does not provide `getfacl`.


## First Step Before Implementation

Review `AGENTS.md` and follow its repository directives. That has been done for this task.


## Current State

- `auto_updater.run_preflight_checks()` always calls `lib_environment_checker.check_default_directory_facls(...)` after `determine_group()`.
- `determine_environment_type()` currently returns only `local`, `staging`, or `production`, based on hostname prefixes.
- The ACL checker itself directly shells out to `getfacl`, so local macOS runs will fail before the updater reaches the rest of preflight.


## Recommendation

Add a small OS-gating helper in `lib/lib_environment_checker.py` and use it in preflight to decide whether the ACL check should run.

Recommended shape:

```python
def should_check_default_directory_facls(environment_type: str) -> bool:
```

Behavior:

- Return `False` for `environment_type == 'local'`.
- For non-local hosts, separately detect whether the OS is RedHat.
- Return `True` only when both conditions are satisfied.
- Keep `check_default_directory_facls()` focused on ACL validation only; do not bury environment-detection logic inside it.

FEEDBACK:
- Return `False` if `environment_type` is anything other than `production` or `staging`.
- Return `True` if `environment_type` is `production` or `staging` -- regardless of OS. No need for the RedHat check.


## Why This Shape

- It keeps the skip decision near preflight orchestration, where the other environment-dependent decisions already live.
- It respects the current meaning of `environment_type`, which is deployment role, not OS family.
- It avoids treating `staging` or `production` as synonyms for "RedHat", which would be broader than the stated goal.
- It gives tests a narrow seam to patch without needing to mock `getfacl` for local-only scenarios.


## RedHat Detection

Use explicit OS detection rather than hostname prefixes alone. `determine_environment_type()` should stay responsible only for returning `local`, `staging`, or `production`; it should not be expanded to return OS-specific values like `redhat`.

Recommended approach:

1. Add a helper that inspects `/etc/redhat-release`.
2. Treat its presence as the RedHat signal.
3. Return `False` if the file is absent.

Why this approach:

- It is simple and matches the deployment target directly.
- It cleanly excludes macOS local development.
- It avoids changing the meaning of `environment_type`.
- It avoids assuming every `staging` or `production` host is RedHat forever.

Alternative:

- `platform.system() == 'Linux'` is too broad for the stated requirement.


## Proposed Code Changes

### 1. Add a gating helper

File: `lib/lib_environment_checker.py`

Add a helper such as:

```python
def should_check_default_directory_facls(environment_type: str) -> bool:
```

Implementation outline:

- if `environment_type == 'local'`: return `False`
- else:
  - check whether `Path('/etc/redhat-release').exists()`
  - return that boolean

This keeps the existing environment-type API intact while layering OS detection on top of it.

This helper should log its decision at `info` level so the skip is visible in updater logs.


### 2. Gate the existing ACL check in preflight

File: `auto_updater.py`

Replace the unconditional call:

```python
lib_environment_checker.check_default_directory_facls(project_path, group, project_email_addresses)
```

with:

```python
if lib_environment_checker.should_check_default_directory_facls(environment_type):
    lib_environment_checker.check_default_directory_facls(project_path, group, project_email_addresses)
```

This preserves the existing ACL-check implementation and error handling on RedHat while skipping it elsewhere.


### 3. Keep `check_default_directory_facls()` unchanged unless needed

File: `lib/lib_environment_checker.py`

The ACL checker already handles:

- missing `getfacl`
- non-zero return code
- missing expected ACL line

Those behaviors are still correct when the function is called on RedHat only, so no functional rewrite is needed unless log wording should mention the RedHat-only scope.


## Tests To Add Or Update

### 1. New helper tests

File: `tests/test_environment_checks.py`

Add focused tests for `should_check_default_directory_facls()`:

- returns `False` for `local` without checking RedHat state
- returns `True` for `staging` when `/etc/redhat-release` exists
- returns `True` for `production` when `/etc/redhat-release` exists
- returns `False` for non-local when `/etc/redhat-release` does not exist

Testing approach:

- patch `lib.lib_environment_checker.Path.exists`


### 2. Preflight orchestration tests

File: `tests/test_auto_updater.py`

Update common patches to include:

```python
patch('auto_updater.lib_environment_checker.should_check_default_directory_facls', return_value=True)
```

Add focused orchestration coverage for:

- ACL check is called when helper returns `True`
- ACL check is not called when helper returns `False`


### 3. Existing ACL function tests

File: `tests/test_environment_checks.py`

Keep the existing `check_default_directory_facls()` tests. They still cover the validation logic itself and should not need semantic changes.


## Expected Outcome

- Local macOS development no longer attempts to run `getfacl`.
- RedHat staging/production hosts still enforce the ACL preflight check.
- The RedHat-only requirement is captured in one explicit helper instead of overloading `determine_environment_type()` with OS semantics.


## Validation

After implementation, run:

```bash
uv run ./run_tests.py
```

If more targeted execution is needed, run the environment-check and auto-updater test modules first.
