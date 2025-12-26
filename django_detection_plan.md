# Plan: Fix Django update detection from uv.lock diff

## Summary
The current detection in `lib/lib_django_updater.py::check_for_django_update()` looks for lines containing `"+django=="`, which matches a `requirements.txt`-style diff but not a `uv.lock` unified diff. The `uv.lock` diff is TOML-like and shows package sections such as:

```
[[package]]
 name = "django"
-version = "4.2.20"
+version = "4.2.27"
```

Because of this mismatch, the function incorrectly returns `False` even when Django is updated (as seen in the provided log). We will replace this logic with uv.lock-aware parsing that detects a version bump within the `[[package]]` section where `name = "django"`.

## Root cause
- `check_for_django_update()` searches for the literal substring `+django==` in the diff text.
- `UvUpdater.compare_uv_lock_files()` returns a unified diff of `uv.lock`, not of `requirements.txt`.
- In `uv.lock` diffs, Django updates appear via `-version = "X"` and `+version = "Y"` lines within the `[[package]]` section for `name = "django"`.

## Proposed changes

1) Update `lib/lib_django_updater.py`
- Replace the simplistic `+django==` check with a uv.lock-diff-aware parser.
- Add a helper function (or embed logic) to:
  - Iterate through unified diff lines.
  - Track when we are inside a `[[package]]` block for Django. Use case-insensitive match on `name = "django"` while taking into account the leading diff markers:
    - Space (` `) means context lines.
    - `-` means removed lines (old file).
    - `+` means added lines (new file).
  - When inside Django’s package block, capture a pair of lines matching `-version = "..."` and `+version = "..."` and compare values.
  - If the version differs, return `True` and optionally the old/new versions for future logging.
  - If only wheels/hashes changed or the version remains identical, return `False`.
- Suggested signature update for internal helper for extensibility:
  - `def parse_uv_lock_version_change(diff_text: str, package_name: str) -> tuple[bool, str | None, str | None]: ...`
  - `check_for_django_update()` will call it with `package_name="django"` and return just the boolean for now, preserving the external API expected by callers.
- Keep docstrings present tense; ensure logging remains informative.

2) Update tests in `requirements-auto-updater/tests/test_django_updater.py`
- Replace tests that rely on `+django==` assumptions with uv.lock-style diffs.
- Add test cases:
  - Checks that a version bump in Django’s package block returns True.
  - Checks that only wheel/hash changes return False.
  - Checks that same version (no change) returns False.
  - Checks case-insensitive matching for `name = "Django"`.
  - Keep docstrings starting with "Checks..." per `AGENTS.md`.

3) No change required in `requirements-auto-updater/auto_updater.py`
- The calling code already uses `compare_result['diff']` and passes it to `check_for_django_update(diff_text)`.
- Once `check_for_django_update()` is uv.lock-aware, downstream behavior (collectstatic + restart) will trigger correctly when Django is updated.

## Parsing approach details
- Iterate line by line through `diff_text.splitlines()`.
- Maintain two trackers:
  - `in_package_block: bool` for `[[package]]` section.
  - `current_package_name: str | None` derived from the latest ` name = "..."` line observed inside a block (accept diff markers ` `, `-`, `+`; strip marker and surrounding whitespace before checking).
- On encountering a line that, after stripping the diff marker and whitespace, equals `[[package]]`, set `in_package_block = True` and reset `current_package_name`.
- When inside a block and a stripped line starts with `name =`, parse the quoted value to update `current_package_name`.
- Only when `current_package_name.lower() == 'django'` should we inspect version lines.
- Collect the most recent `-version = "..."` and `+version = "..."` seen for the Django block. If both present and different, conclude `True`.
- Stop early on positive detection for efficiency.

## Edge cases handled
- Multiple package blocks; only act inside the Django block.
- Case-insensitive package name match (`Django`, `django`).
- Extra spaces or different quote styles are unusual but we’ll focus on the typical `name = "..."` TOML style as produced by uv.
- Diffs where only wheels, sdist, or hash entries change: return False.
- Diffs where `[[package]]` or `name = "django"` appear only on context lines (leading space) — still valid for determining the package block.

## Logging
- Keep `INFO` level start/end markers similar to existing style.
- On detection, log the old/new versions for traceability, e.g., `ok / django version updated: 4.2.20 -> 4.2.27`.
- On no detection, log `ok / django-updated, ``False``` as today for backward consistency.

## Validation plan
- Run unit tests via the existing test harness after updates.
- Add unit tests for wheels-only changes and case-insensitivity.
- Manual smoke test: feed the exact diff captured in the log into the function and confirm it returns True.

## Out of scope
- Email contents and templates.
- Broader refactors in uv comparison or git handling.
- Making `collectstatic` path handling more robust (already marked TODO elsewhere).
