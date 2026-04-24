# PLAN: Add `getfacl` Check To Environmental Scan

## Goal

Add a new preflight/environmental check that verifies the target project directory has the expected default ACLs set, using `getfacl`, and handle failures the same way as the existing environmental checks in [`lib/lib_environment_checker.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/lib/lib_environment_checker.py) do: log, email, and raise.


## Relevant Existing Pattern

- Preflight orchestration lives in [`auto_updater.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/auto_updater.py), in `run_preflight_checks()`.
- The environmental checker functions live in [`lib/lib_environment_checker.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/lib/lib_environment_checker.py).
- Existing checker functions follow a consistent pattern:
  - log start
  - perform a focused validation
  - on failure: create message, send email, raise `Exception`
  - on success: log `ok / ...`
- Unit tests for these checks live in [`tests/test_environment_checks.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/tests/test_environment_checks.py).
- `run_preflight_checks()` is also mocked in [`tests/test_auto_updater.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/tests/test_auto_updater.py), so adding a new checker there will require updating the common patch set.


## Recommendation

Add a new function in `lib_environment_checker.py`, tentatively:

```python
def check_default_directory_facls(
    project_path: Path, expected_group: str, project_email_addresses: list[tuple[str, str]]
) -> None:
```

This function should:

1. Run `getfacl` against `project_path`.
2. Parse stdout.
3. Verify that the project directory includes default ACL entries indicating new descendants will inherit group-writeable access for the expected group.
4. On failure, follow the same email-and-raise pattern used by the other environmental checks.


## Recommended Placement In Preflight Sequence

Recommended order in `run_preflight_checks()`:

1. `validate_project_path()`
2. `determine_project_email_addresses()`
3. `check_branch()`
4. `check_git_status()`
5. `validate_pyproject_toml()`
6. `determine_environment_type()`
7. `validate_uv_path()`
8. `determine_group()`
9. `check_default_directory_facls()`
10. `check_group_and_permissions()`

### Why place it there

- It depends on `group`, so it should come after `determine_group()`.
- It should run before the recursive group/permission scan, because ACL misconfiguration is the more structural/root-cause problem.
- If ACLs are missing, the later file-permission failure is often just a downstream symptom, especially for `.venv/__pycache__` files.

### Alternative

It would also be defensible to place the ACL check immediately after `validate_project_path()`, but only if the function determines the expected group internally. I do not recommend that, because it duplicates responsibility already handled by `determine_group()`.


## Evaluation: Check Only The Project Directory?

Recommendation: yes, checking the project root directory only is sufficient for this implementation.

### Reasoning

- Your intended remediation command applies default ACLs recursively to directories:

```bash
find "$PROJECT_DIR_PATH" -type d -exec sudo setfacl -m d:g:"$GROUP":rwX,d:m::rwX {} +
```

- If that command is the standardized operational fix on these servers, then verifying the root project directory is a practical proxy for the intended server state.
- The issue described is specifically about inheritance for newly created files and directories. That is exactly what default ACLs on directories are for.
- In your environment, server setup is centrally controlled, so there is less value in trying to support multiple ACL layouts or per-subtree exceptions.

### Limitation

Checking only `project_path` does not prove every nested directory also has the same default ACLs. It proves only that the root is configured. If someone later applies ACLs inconsistently deeper in the tree, this check would miss that.

### Practical judgment

That tradeoff is acceptable here. The goal is an environmental scan that catches the common real-world misconfiguration without adding a heavy recursive ACL audit.


## Evaluation: Use `getfacl` For Verification?

Recommendation: yes, `getfacl` is the right verification mechanism.

### Why

- Standard file mode bits from `stat()` / `ls` do not show default ACL entries.
- The problem you are trying to detect is specifically ACL-backed inheritance behavior, not just current chmod state.
- `getfacl` is the canonical system tool for inspecting ACLs, so it matches the operational fix and the admin mental model.

### Implementation note

Do not parse for one exact full output block. Parse only the required signals, because:

- output ordering may vary slightly by system
- the named group ACL line may differ if the group name is unexpected
- extra ACL entries may exist and should not automatically fail the check

The check should look for the minimum required entries, likely:

- `default:group:{expected_group}:rwx` or `default:group:{expected_group}:rw-`/`rwx` depending on platform normalization
- `default:mask::rwx` or at least a mask that preserves write access

Because your `setfacl` command uses `rwX`, the displayed execute bit may depend on directory semantics. For a directory target, expecting `rwx` is reasonable.


## Proposed Failure Criteria

Fail the environmental check when any of the following is true:

1. `getfacl` is not available or cannot be executed.
2. `getfacl` exits non-zero for `project_path`.
3. The output does not contain the expected default ACL entry for the inferred group.
4. The output indicates default ACLs are absent entirely.

Recommended message shape:

```text
Error: Default ACL check failed for project directory.
```

Append useful diagnostics, for example:

- project path
- expected group
- `getfacl` stderr/stdout snippet
- which required ACL entry was missing

This should be short enough for email but specific enough that the remediation is obvious.


## Proposed Parsing Strategy

Keep parsing simple and explicit.

### Option A: direct line membership check

Parse stdout into stripped lines and require:

```python
required_line = f'default:group:{expected_group}:rwx'
```

This is the best first version if your servers are consistent.

### Option B: slightly more tolerant parse

Accept any line matching:

- prefix: `default:group:{expected_group}:`
- permissions containing `rw`

This is more defensive if you want to avoid coupling to exact execute-bit rendering.

### Recommendation

Start with Option A unless you already know `getfacl` output varies across your fleet. The repo’s current checker style is straightforward and explicit; overly abstract parsing would be out of character.


## Proposed Code Changes

### 1. Add new checker function

File: [`lib/lib_environment_checker.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/lib/lib_environment_checker.py)

Add:

- `check_default_directory_facls(...)`

Implementation shape:

- log start
- call `subprocess.run(['getfacl', str(project_path)], capture_output=True, text=True, check=False)`
- inspect return code and stdout
- if ACL requirement missing:
  - build message
  - send email to `project_email_addresses`
  - raise `Exception`
- else log success

### 2. Call it from preflight

File: [`auto_updater.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/auto_updater.py)

Insert after:

```python
group: str = lib_environment_checker.determine_group(project_path, project_email_addresses)
```

and before:

```python
lib_environment_checker.check_group_and_permissions(project_path, group, project_email_addresses)
```

### 3. Add unit tests

File: [`tests/test_environment_checks.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/tests/test_environment_checks.py)

Add focused tests for:

- success when `getfacl` output contains the expected default group ACL
- failure when `getfacl` output has no default ACL block
- failure when `getfacl` exits non-zero
- optional: failure when default ACL exists for a different group

Testing approach:

- patch `lib.lib_environment_checker.subprocess.run`
- patch `lib.lib_environment_checker.Emailer.send_email`
- assert success path does not email
- assert failure path emails once and raises

### 4. Update preflight orchestration tests

File: [`tests/test_auto_updater.py`](/Users/birkin/Documents/Brown_Library/auto_updater_stuff/requirements-auto-updater/tests/test_auto_updater.py)

Update the common dependency patch helper to include:

```python
patch('auto_updater.lib_environment_checker.check_default_directory_facls', return_value=None)
```

Without that, tests that mock the existing preflight chain will break when the new call is added.


## Suggested Function Contract

Suggested behavior:

- Input:
  - `project_path`
  - `expected_group`
  - `project_email_addresses`
- Output:
  - returns `None` on success
- Failure:
  - logs exception message
  - emails project admins
  - raises `Exception`

This exactly matches the current environmental-check pattern.


## Suggested Error Message Content

Recommended wording:

```text
Error: Default ACL check failed for project directory ``/path/to/project``.
Expected default ACL entry for group ``THE_GROUP`` was not found.
```

If command execution failed, prefer:

```text
Error: Default ACL check failed for project directory ``/path/to/project``.
Unable to run `getfacl`: ...
```


## Risks / Edge Cases

- `getfacl` may not be installed on some systems.
  - Recommendation: treat that as a failed environmental prerequisite.
- Some ACL output may include effective permissions or additional named entries.
  - Recommendation: ignore extra lines and check only required lines.
- Group inference via `determine_group()` is based on `ls -l` output and “most common group”.
  - That is already an existing assumption in this codebase, so the new check should reuse it rather than invent a second source of truth.


## Final Recommendation

Implement the ACL check as a new dedicated environmental-check function in `lib_environment_checker.py`, call it after `determine_group()` and before `check_group_and_permissions()`, and verify only the project root directory with `getfacl`.

That gives you:

- a targeted early failure for the root-cause ACL problem
- behavior consistent with the existing notification/exception pattern
- low implementation complexity
- a practical signal for the real issue you are seeing with newly created `.venv` cache files


## Implementation Sequence

1. Add `check_default_directory_facls()` to `lib_environment_checker.py`.
2. Wire it into `run_preflight_checks()` in `auto_updater.py`.
3. Add unit tests in `tests/test_environment_checks.py`.
4. Update `tests/test_auto_updater.py` mocks for the new preflight call.
5. Run `uv run ./run_tests.py`.
