# Auto-Updater Flow Analysis

**Analysis Date:** 2025-12-30

## Overview

This document analyzes the `auto_updater.py` implementation against the documented flow in `README.md` to identify any missing or incomplete functionality.

For any code-changes, refer to `requirements-auto-updater/AGENTS.md`.

---

## Flow Coverage - What's Implemented

The `manage_update()` function implements most of the documented flow:

### ✅ Initial Checks (lines 101-126)
- Validates project path
- Determines admin emails
- Checks branch
- Checks git status
- Determines environment type (local/staging/production)
- Validates uv path
- Determines group
- Checks group and permissions

### ✅ Initial Tests (line 126)
- Runs project's `run_tests.py`
- Emails admins and exits on failure

### ✅ Update Process (lines 129-135)
- Backs up `uv.lock` to `../requirements_backups/uv.lock_ISODATETIME`
- Runs `uv sync --upgrade --group staging` (dev) or `uv sync --upgrade --group production` (prod)
- Compares old and new `uv.lock` files

### ✅ Post-Update Actions When Changes Detected (lines 137-163)
- Runs followup tests
- Checks for Django updates and runs `collectstatic` if needed
- Runs `touch ./config/tmp/restart.txt` for Passenger reload
- Handles git operations (add, commit, push)
- Sends email with diff to project admins

### ✅ Cleanup (line 167)
- Updates group and permissions on venv and requirements_backups directories

---

## Missing or Incomplete Steps

### ✅ 1. Python Version Validation
**README Reference:** Line 40 - "ensures a python version is listed"

**Status:** Implemented

**Details:** 
- Validation implemented in `lib_environment_checker.validate_pyproject_toml()`
- Checks for `requires-python` field in `[project]` section of `pyproject.toml`
- Validates that the field exists and is a non-empty string
- Emails project admins and exits on validation failure
- Comprehensive test coverage in `tests/test_environment_checks.py`

**Implementation:** Added in validate_pyproject_toml() function, called after git status check and before environment type determination

---

### ⚠️ 2. Test Failure Rollback Logic
**README Reference:** Lines 59-63

**Expected Behavior:**
```
- on test failure
    - restores original `uv.lock`
    - runs `uv sync --frozen`  # just updates the `.venv` from the `uv.lock` file
    - runs project's `run_tests.py` again
    - emails the canceled-diff (and test-failures) to the project-admins
```

**Current Implementation:**
- Lines 151-152 capture `followup_tests_problems` but don't handle rollback
- If tests fail, code still proceeds to git commit (line 155) and email (line 162)
- No restoration of original `uv.lock`
- No `uv sync --frozen` execution
- No re-run of tests after rollback

**Impact:** HIGH - This is a critical safety feature. If post-update tests fail, the broken `uv.lock` gets committed to the repository instead of being rolled back.

**Required Implementation:**
```python
# After line 152, need to add:
if followup_tests_problems is not None:
    log.warning('Post-update tests failed; initiating rollback')
    
    # 1. Restore original uv.lock from backup
    # Note: backup is at project_path.parent / 'uv.lock.bak' (created by UvUpdater.backup_uv_lock)
    import shutil
    backup_path = project_path.parent / 'uv.lock.bak'
    shutil.copy(backup_path, project_path / 'uv.lock')
    log.info('Restored original uv.lock from backup')
    
    # 2. Run uv sync --frozen to update .venv from restored uv.lock
    # Must include --group flag with environment_type
    sync_command = [str(uv_path), 'sync', '--frozen', '--group', environment_type]
    subprocess.run(sync_command, cwd=str(project_path), check=True)
    log.info('Synced .venv from restored uv.lock')
    
    # 3. Re-run tests to verify restoration worked
    verification_result = run_followup_tests(uv_path, project_path)
    if verification_result is not None:
        log.error('Tests still failing after rollback - environment may be corrupted')
    else:
        log.info('Tests passing after rollback - environment successfully restored')
    
    # 4. Email about rollback (modify send_email_of_diffs to handle rollback scenario)
    # Need to create a new email type or modify existing to indicate rollback occurred
    rollback_problems = {
        'collectstatic_problems': None,
        'test_problems': followup_tests_problems,
        'git_problems': None,
        'rollback_occurred': True,
        'verification_result': verification_result
    }
    send_email_of_diffs(project_path, diff_text, rollback_problems, project_email_addresses)
    
    # 5. Skip git operations and continue to cleanup
    # Update permissions (line 174) will still run
    log.info('Skipping git operations due to test failure and rollback')
    update_group_and_permissions(project_path, uv_lock_backup_path, group)
    return  # Exit without git commit/push
```

**Additional Changes Needed:**
1. **Import shutil** at top of `auto_updater.py` (currently not imported)
2. **Modify `lib_emailer.py`** to handle rollback scenario:
   - Update `send_email_of_diffs()` to check for `rollback_occurred` flag
   - Create new email message type or modify `create_update_problem_message()` to indicate rollback
   - Include verification test results in email
3. **Consider**: Should collectstatic be run AFTER tests pass, not before?
   - Current flow: tests → collectstatic → git
   - If collectstatic fails, we don't rollback (only test failures trigger rollback)
   - This seems inconsistent with the safety-first approach

---

### ⚠️ 3. No-Changes Scenario
**README Reference:** Lines 49-50

**Current Behavior:**
- When `compare_result['changes']` is False (line 139), code skips to cleanup
- No email notification sent to admins

**Impact:** Low - This is intentional to reduce email noise from cron jobs

**Note:** May want to add optional logging or periodic "all clear" emails

---

### ⚠️ 4. Touch Command Robustness
**README Reference:** Line 56

**Current Implementation:** Line 146
```python
subprocess.run(['touch', './config/tmp/restart.txt'], check=True)  # TODO: make this more robust
```

**Issues:**
- Uses `check=True` which raises exception if path doesn't exist
- Hardcoded path may not exist in all Django projects
- TODO comment acknowledges this needs improvement

**Impact:** Medium - Could cause failures in projects with different directory structures

**Recommendations:**
- Check if path exists before touching
- Make path configurable via environment variable
- Handle non-Django projects gracefully

---

### ✅ 5. Error Handling for Git Operations — RESOLVED (2026-01-01)
**Current Implementation:** Lines 154-160
```python
git_handler = GitHandler()
git_success, git_message = git_handler.manage_git(project_path, diff_text)
followup_git_problems: None | str = None
if not git_success:
    followup_git_problems = git_message
    log.warning(f'Git operations failed: {git_message}')
```

**Resolution:**
- `GitHandler.manage_git()` now returns `tuple[bool, str]` for proper error propagation
- Caller captures return values and handles failures appropriately
- Git errors are logged and added to `followup_problems` dictionary
- Email notifications include git failure information
- Each git operation (pull, add, commit, push) is validated before proceeding to the next
- Special handling for "nothing to commit" as a success case

**Previous Concern:**
- No visible error handling if git operations fail
- Git failures could leave repository in inconsistent state

---

## Priority Recommendations

### 🔴 Critical Priority
1. **Implement test failure rollback logic** - This is the most significant gap. Without it, failed updates get committed to the repository.

### 🟡 Medium Priority
2. **Improve touch command robustness** - Make it configurable and handle missing paths gracefully

### 🟢 Low Priority
4. **Implement Python-version / pyproject.toml check** - DONE.
5. **Consider no-changes notification** - Decide if periodic "all clear" emails are valuable

---

## Conclusion

The implementation is quite solid overall and covers most of the documented flow. However, the **test failure rollback mechanism** is a critical missing piece that should be implemented before relying on this tool in production. Without it, there's a risk of committing broken dependencies to the repository when post-update tests fail.

The other issues are less critical but should be addressed to improve robustness and maintainability.
