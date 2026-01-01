# Rollback Test Plan

## Overview
This document assesses the test coverage for the newly implemented rollback functionality in `auto_updater.py` and `lib/lib_emailer.py`.

## Rollback Code Review Summary

### Implementation in `auto_updater.py` (lines 155-193)
The rollback logic triggers when `followup_tests_problems is not None` and performs:
1. Restores original `uv.lock` from backup using `shutil.copy()`
2. Runs `uv sync --frozen --group {environment_type}` to restore `.venv`
3. Re-runs tests via `run_followup_tests()` to verify restoration
4. Sends rollback notification email with verification results
5. Skips git commit/push operations
6. Continues to cleanup (permissions update)
7. Returns early from `manage_update()`

### Implementation in `lib/lib_emailer.py` (lines 40-71, 143-175)
Email handling enhancements:
- `send_email_of_diffs()` detects `rollback_occurred` flag in `followup_problems` dict
- New `create_rollback_message()` method creates distinct rollback email with:
  - Clear "ROLLBACK PERFORMED" header
  - Original test failure details
  - Verification test results (✓ passing or ✗ still failing)
  - Attempted (but not applied) diff
  - Action items for admins

## Existing Test Coverage Analysis

### Current Test Files
1. **`test_environment_checks.py`** (696 lines, 33+ tests)
   - Comprehensive coverage of environmental validation
   - Tests email sending via mocking
   - Tests error handling and exception raising
   
2. **`test_django_updater.py`** (77 lines, 4 tests)
   - Tests Django version detection in diffs
   
3. **`test_uv_updater.py`** (72 lines, 2 tests)
   - Tests `compare_uv_lock_files()` happy path and error handling
   
4. **`test_misc.py`** (135 lines, 1 active test)
   - Tests git operations with mocking

### Coverage Gaps for Rollback Functionality

The rollback implementation is **NOT currently tested**. The existing tests focus on:
- Individual helper functions in isolation
- Environmental validation checks
- Git operations
- File comparison utilities

**No tests exist for:**
- The main `manage_update()` orchestration function
- The rollback flow triggered by test failures
- Email message generation for rollback scenarios
- Integration between rollback steps

## Recommended Additional Tests

### Priority: HIGH

#### 1. **Rollback Flow Integration Test**
**File:** `tests/test_rollback_integration.py` (new file)

**Test:** `test_rollback_on_post_update_test_failure()`
- **Purpose:** Verify complete rollback flow when post-update tests fail
- **Setup:**
  - Create temp project directory with mock `pyproject.toml`, `uv.lock`, `.venv`
  - Mock `run_followup_tests()` to return failure on first call, success on second
  - Mock `subprocess.run()` for `uv sync --frozen`
  - Mock `send_email_of_diffs()`
- **Assertions:**
  - `shutil.copy()` called to restore `uv.lock` from backup
  - `subprocess.run()` called with correct `uv sync --frozen --group` command
  - `run_followup_tests()` called twice (initial failure, verification)
  - `send_email_of_diffs()` called with `rollback_occurred=True`
  - Git operations NOT called (no `GitHandler.manage_git()`)
  - `update_group_and_permissions()` still called
  - Function returns early (doesn't continue to git operations)

**Test:** `test_rollback_verification_still_failing()`
- **Purpose:** Verify handling when verification tests also fail after rollback
- **Setup:** Similar to above, but mock `run_followup_tests()` to fail both times
- **Assertions:**
  - Rollback still completes
  - Email sent with `verification_result` containing failure message
  - Appropriate error logging occurs

**Test:** `test_rollback_sync_command_failure()`
- **Purpose:** Verify handling when `uv sync --frozen` fails during rollback
- **Setup:** Mock `subprocess.run()` to raise `CalledProcessError`
- **Assertions:**
  - Error logged with `e.stderr`
  - Verification tests still attempted
  - Email still sent
  - Function completes without crashing

#### 2. **Rollback Email Message Tests**
**File:** `tests/test_emailer_rollback.py` (new file)

**Test:** `test_create_rollback_message_with_passing_verification()`
- **Purpose:** Verify rollback email format when verification tests pass
- **Setup:**
  - Create `Emailer` instance with temp project path
  - Call `create_rollback_message()` with `verification_result=None`
- **Assertions:**
  - Message contains "ROLLBACK PERFORMED"
  - Message contains "✓ Tests are now passing after rollback"
  - Message contains original test failure text
  - Message contains diff text
  - Message contains "Action required"
  - Message does NOT contain "WARNING"

**Test:** `test_create_rollback_message_with_failing_verification()`
- **Purpose:** Verify rollback email format when verification tests fail
- **Setup:**
  - Create `Emailer` instance
  - Call `create_rollback_message()` with `verification_result="test output"`
- **Assertions:**
  - Message contains "ROLLBACK PERFORMED"
  - Message contains "✗ WARNING: Tests are still failing"
  - Message contains verification test output
  - Message contains "environment may be corrupted"

**Test:** `test_send_email_of_diffs_routes_to_rollback_message()`
- **Purpose:** Verify `send_email_of_diffs()` correctly routes to rollback message
- **Setup:**
  - Mock `Emailer.send_email()`
  - Call with `followup_problems={'rollback_occurred': True, ...}`
- **Assertions:**
  - `create_rollback_message()` called (not `create_update_problem_message()`)
  - Email sent with correct recipients

### Priority: MEDIUM

#### 3. **Rollback Edge Cases**
**File:** `tests/test_rollback_integration.py`

**Test:** `test_no_rollback_when_tests_pass()`
- **Purpose:** Verify normal flow continues when post-update tests pass
- **Setup:** Mock `run_followup_tests()` to return `None` (success)
- **Assertions:**
  - Rollback code NOT executed
  - Git operations ARE called
  - Normal success email sent (not rollback email)

**Test:** `test_rollback_with_collectstatic_failure_before_tests()`
- **Purpose:** Verify rollback only triggers on test failure, not collectstatic
- **Setup:**
  - Mock Django update detected
  - Mock `run_collectstatic()` to return failure
  - Mock `run_followup_tests()` to return failure
- **Assertions:**
  - Rollback triggered by test failure
  - Both collectstatic and test problems included in context

**Test:** `test_rollback_backup_file_missing()`
- **Purpose:** Verify handling when `uv.lock.bak` doesn't exist
- **Setup:** Don't create backup file before rollback attempt
- **Assertions:**
  - `shutil.copy()` raises appropriate exception
  - Error is logged or handled gracefully

#### 4. **Environment Type Handling in Rollback**
**File:** `tests/test_rollback_integration.py`

**Test:** `test_rollback_uses_correct_environment_group()`
- **Purpose:** Verify `--group` flag uses correct environment type in rollback
- **Setup:** Test with different `environment_type` values ('staging', 'prod', 'local')
- **Assertions:**
  - `uv sync --frozen --group staging` for staging
  - `uv sync --frozen --group prod` for production
  - `uv sync --frozen --group local` for local

### Priority: LOW

#### 5. **Logging Verification**
**File:** `tests/test_rollback_integration.py`

**Test:** `test_rollback_logging_messages()`
- **Purpose:** Verify appropriate log messages during rollback
- **Setup:** Capture log output during rollback
- **Assertions:**
  - "Post-update tests failed; initiating rollback" logged at WARNING
  - "Restored original uv.lock from backup" logged at INFO
  - "Synced .venv from restored uv.lock" logged at INFO
  - "Tests passing after rollback" or "Tests still failing" logged appropriately
  - "Skipping git operations due to test failure and rollback" logged at INFO

## Test Implementation Considerations

### Following Repository Standards (from `AGENTS.md`)

1. **Use `unittest` framework** (not pytest) - matches existing tests
2. **Test docstrings start with "Checks..."** - per repository convention
3. **Use Python 3.12 type hints** - `def test_name() -> None:`
4. **Mock external dependencies** - `subprocess.run()`, file operations, email sending
5. **Use `TemporaryDirectory`** - for file system operations
6. **Test both happy path and failure cases** - per line 78-80 of AGENTS.md

### Mocking Strategy

Key functions to mock in rollback tests:
- `run_followup_tests()` - to simulate test failures/successes
- `subprocess.run()` - to avoid actual `uv sync` commands
- `shutil.copy()` - to verify file restoration without actual file ops (optional)
- `send_email_of_diffs()` - to verify email sending without SMTP
- `GitHandler.manage_git()` - to verify git operations skipped
- `update_group_and_permissions()` - to verify cleanup still occurs

### Test Data Requirements

Minimal test fixtures needed:
- Mock `pyproject.toml` with valid structure
- Mock `uv.lock` and `uv.lock.bak` files
- Mock `.venv` directory structure
- Mock test failure output strings
- Mock diff text

## Summary

### Current State
- **0 tests** directly cover the rollback functionality
- Existing tests cover individual components but not integration

### Recommended Tests
- **HIGH priority:** 6 tests (rollback flow, email routing, verification scenarios)
- **MEDIUM priority:** 4 tests (edge cases, environment handling)
- **LOW priority:** 1 test (logging verification)
- **Total recommended:** 11 new tests

### Rationale for Testing
The rollback functionality is a **critical safety feature** (marked HIGH impact in `FLOW_ANALYSIS.md`). Without tests:
- Regressions could go undetected
- Edge cases may not be handled correctly
- Refactoring becomes risky
- Confidence in production deployment is reduced

### Implementation Approach
1. Start with HIGH priority integration test for main rollback flow
2. Add email message tests to verify user communication
3. Add edge case tests for robustness
4. Consider adding tests incrementally as issues are discovered

## Notes

- The rollback code follows good practices (explicit logging, error handling)
- The implementation is straightforward, which makes it testable
- Most complexity is in orchestration, not individual operations
- Mocking will be essential to avoid actual file/subprocess operations
- Tests should verify the **sequence** of operations, not just individual calls
