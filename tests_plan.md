# Plan to get tests running

## Findings
- Project dir: `requirements-auto-updater/`
- Tests dir: `requirements-auto-updater/tests/`
  - `test_main.py` (contains multiple `unittest.TestCase`s)
  - `test_uv_updater.py` (properly named for discovery)
  - `test_environment_checks.py` (to be added)
- Library code lives under `requirements-auto-updater/lib/`.

### New
- `run_tests.py` exists at the project root and standardizes running tests via `uv` and stdlib `unittest`.


## Recommended command(s) to adopt now (no code changes)

- If running from the `requirements-auto-updater/` directory:

```
uv run ./run_tests.py -v
```

This runs `test_uv_updater.py`, `test_main.py`, and `test_environment_checks.py`.

## Next steps
- Add a short section to `README.md` under "How to run tests" that references `uv run ./run_tests.py -v`.
- Continue finishing tests in `tests/test_main.py`, `tests/test_uv_updater.py`, and `tests/test_environment_checks.py`.
- When stabilizing tests, consider structured assertions around any subprocess output (e.g., `lib_git_handler.run_git_pull()` capturing `stdout`). Do not change code yet; finish tests first.
- Optionally add CI (e.g., GitHub Actions) to run `uv run ./run_tests.py -v` on pushes/PRs.

---

# Test plan: environmental checks in `manage_update()`

This plan adds focused, actionable tests (no mocks/patches) for each function invoked in the `## ::: run environmental checks :::` section of `auto_updater.py -> manage_update()`.

## Scope and goals

- Cover each environment check with:
  - a happy path
  - a failure/edge case (when practical without mocks)
- Use stdlib `unittest` per `AGENTS.md`.
- Prefer temporary directories and committed sample files under `tests/sample_files/`.

## Running tests

- From repo root `requirements-auto-updater/`:

```
uv run ./run_tests.py -v
```

Note: `lib/lib_emailer.py` imports `python-dotenv`. Ensure it's available in the test environment (it is declared elsewhere in this repo).

## New test module

- Add `tests/test_environment_checks.py` to contain these tests. Keep existing tests intact.

## Handling email on failure paths (no mocks)

Several failure paths send email via `lib.lib_emailer.Emailer`. With Python 3.12, the legacy `smtpd` module is removed. Options:

- Do not start any SMTP server. Tests should still assert that an exception is raised on failure paths without asserting on the exact error message, since the SMTP connection error may be raised before the function raises its own application-level exception.

The repo-level `.env` already points to `localhost:1026` for email.

## Sample files/fixtures to add under `tests/sample_files/`

- `email_parent_env/.env`
  - Minimal file containing `ADMINS_JSON`, for example:
    ```
    ADMINS_JSON='[["Project Admin", "project_admin@example.com"]]'
    ```
- `git_head_main/.git/HEAD`
  - Content: `ref: refs/heads/main`
- `git_head_feature/.git/HEAD`
  - Content: `ref: refs/heads/feature/test`

Prefer ephemeral temp directories for permissions/group and git-status tests, since those need FS metadata and/or a real git repo.

## Per-function test plan

Each item maps to a call in `manage_update()` under the environmental checks section.

1) `lib_environment_checker.validate_project_path(project_path: Path) -> None`

Done.

2) `lib_environment_checker.determine_project_email_addresses(project_path: Path) -> list[tuple[str, str]]`

Done.

3) `lib_environment_checker.check_branch(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None`

Done.

4) `lib_environment_checker.check_git_status(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None`

Done.

5) `lib_environment_checker.determine_environment_type(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> str`

Done.

6) `lib_environment_checker.validate_uv_path(uv_path: Path, project_path: Path) -> None`

Done.

7) `lib_environment_checker.determine_group(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> str`

Done.

8) `lib_environment_checker.check_group_and_permissions(project_path: Path, expected_group: str, project_email_addresses: list[tuple[str, str]]) -> None`

- Paths examined:
  - `project_path / '.venv'`
  - `project_path / '../uv.lock.bak'`
- Happy path:
  - Create `proj_dir/.venv/` and a file; set group-write on dirs/files.
  - Create `uv.lock.bak` in the parent of `proj_dir` and set group-write.
  - Determine `expected_group` via `grp`; call function; expect no exception.
- Failure path:
  - Remove group-write from one `.venv` file; call function; assert exception.

## Test module structure (high level)

- `tests/test_environment_checks.py`:
  - `class TestEnvironmentChecks(unittest.TestCase)` with `setUp`/`tearDown` managing temp dirs and CWD.
  - Optionally `setUpClass`/`tearDownClass` for starting/stopping a local SMTP server (if you choose Option A).
  - One test method per case, e.g.:
    - `test_validate_project_path_ok()` / `test_validate_project_path_missing_raises()`
    - `test_determine_project_email_addresses_ok()` / `test_determine_project_email_addresses_missing_env_raises()`
    - `test_check_branch_main_ok()` / `test_check_branch_non_main_raises()`
    - `test_check_git_status_clean_ok()` / `test_check_git_status_dirty_raises()`
    - `test_determine_environment_type_valid_value()`
    - `test_validate_uv_path_ok()` / `test_validate_uv_path_missing_raises()`
    - `test_determine_group_ok()` / `test_determine_group_invalid_raises()`
    - `test_check_group_and_permissions_ok()` / `test_check_group_and_permissions_perm_issue_raises()`

## Notes and constraints

- Keep CWD hygiene: always restore CWD in `tearDown`.
- Use `tempfile.TemporaryDirectory()` for isolation; write files with `Path.write_text()`, set perms via `Path.chmod()`.
- For git tests, require `git` on PATH; otherwise, skip those tests with a clear message.
- Do not modify application code to enable tests.
