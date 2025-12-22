# Plan: Refactor `UvUpdater.compare_uv_lock_files()` to return a dict

## Summary
Refactor `lib/lib_uv_updater.py::UvUpdater.compare_uv_lock_files()` to return a dictionary of the form `{"changes": bool, "diff": str}` where:
- `changes` indicates whether there are differences between the current `uv.lock` and its backup.
- `diff` contains the unified diff text (or an empty string if no changes or an error occurs).

This replaces the current return type `str | None` with a consistent dict structure and eliminates `None` returns.

---

## Files to update

1) `lib/lib_uv_updater.py`
- Change signature of `compare_uv_lock_files()` from `-> str | None` to `-> dict[str, bool | str]` (more specifically: `-> dict[str, object]` or document the exact keys/types in the docstring; Python 3.12 hints can be `-> dict[str, str | bool]`).
- Update docstring to describe the new return structure, behavior on no-diff and on exception.
- Implementation changes:
  - Compute the unified diff as today.
  - Build `diff_text` by joining lines with newlines, as today.
  - Set `changes: bool = bool(diff)`.
  - Return `{ "changes": changes, "diff": diff_text }` on success.
  - On exception, log the error and return `{ "changes": False, "diff": "" }`.

2) `auto_updater.py`
- Update the call site in `manage_update()`:
  - Replace `diff_text: str | None = uv_updater.compare_uv_lock_files(...)` with `compare_result = uv_updater.compare_uv_lock_files(...)`.
  - Gate behavior on `if compare_result["changes"]:` instead of `if diff_text:`.
  - Set `diff_text = compare_result["diff"]` and pass this to:
    - `lib_django_updater.check_for_django_update(diff_text)`
    - `GitHandler().manage_git(project_path, diff_text)`
    - `send_email_of_diffs(project_path, diff_text, followup_problems, project_email_addresses)`
- Adjust any type hints accordingly.

3) `tests/test_uv_updater.py`
- Update tests to reflect new return type and semantics.
  - `test_compare_uv_lock_files_happy_path_returns_diff`:
    - Call the method to get `result` (dict).
    - Assert `result["changes"] is True`.
    - Assert `result["diff"]` is not empty and includes expected headers and line changes.
  - `test_compare_uv_lock_files_failure_returns_none`:
    - Rename to `test_compare_uv_lock_files_failure_returns_empty_dict` (or similar) to reflect new behavior.
    - Assert the method returns a dict with `{"changes": False, "diff": ""}` when the backup file is missing.
- Ensure all docstrings still start with "Checks..." per `AGENTS.md`.

---

## Notes on behavior and logging
- Maintain existing logging behavior indicating whether differences were found.
- Continue logging the diff at debug-level for traceability.
- On exceptions, avoid raising; instead, return `{ "changes": False, "diff": "" }` and maintain the current error log message.

---

## Backward compatibility considerations
- This is a breaking change for callers that expect `str | None`.
- Current repository callers identified via grep:
  - `auto_updater.py` (single runtime caller) — will be updated.
  - `tests/test_uv_updater.py` (test caller) — will be updated.
- No other usages were found in `requirements-auto-updater/`.

---

## Detailed edit checklist

- `lib/lib_uv_updater.py`
  - Update return type annotation of `compare_uv_lock_files()`.
  - Update docstring to describe the returned dict.
  - Compute `changes = bool(diff)` and return `{ "changes": changes, "diff": diff_text }`.
  - On exception, return `{ "changes": False, "diff": "" }`.

- `auto_updater.py`
  - Change variable name to `compare_result` or similar.
  - Gate on `compare_result["changes"]`.
  - Extract `diff_text = compare_result["diff"]` for downstream calls.
  - Update local type hints if present.

- `tests/test_uv_updater.py`
  - Update assertions:
    - happy path: `self.assertTrue(result["changes"])`, check non-empty `result["diff"]` and expected content.
    - failure path: `self.assertFalse(result["changes"])`, `self.assertEqual(result["diff"], "")`.
  - Optionally rename the failure test to better reflect new expectation.

---

## Validation plan

- Run unit tests:
  - `uv run ./run_tests.py`
- Manual smoke test path (optional):
  - Create temp directory with `uv.lock` and `uv.lock.bak` containing small variations.
  - Instantiate `UvUpdater` and call `compare_uv_lock_files()` to verify returned dict values in both change/no-change cases.

---

## Out of scope
- No changes to email template contents or formatting.
- No changes to how diffs are generated (still using `difflib.unified_diff`).
- No changes to other parts of the update workflow.
