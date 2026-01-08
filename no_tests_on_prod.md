# Plan: Skip Tests on Production Servers

## Overview
This document outlines the plan to modify the auto-updater script to skip test execution on production servers while maintaining the update workflow.

**UPDATE**: After reviewing the code, the `environment_type` variable is already being determined in `lib_environment_checker.py` (line 222-237) based on hostname:
- `'production'` for hostnames starting with 'p'
- `'staging'` for hostnames starting with 'd' or 'q'  
- `'local'` otherwise

This variable should be passed to the test functions instead of re-implementing hostname detection.

## Current Test Execution Flow

### Test Points in `auto_updater.py`
1. **Initial Tests** (Line 129): `run_initial_tests(uv_path, project_path, project_email_addresses)`
   - Runs before any updates to validate environment health
   - On failure: emails admins and raises exception to halt auto-update
   
2. **Follow-up Tests** (Line 152): `run_followup_tests(uv_path, project_path)`
   - Runs after virtualenv updates
   - On failure: returns error message but continues processing (for rollback/email/permissions)

### Environment Type Determination
- Line 120 in `auto_updater.py`: `environment_type = lib_environment_checker.determine_environment_type(...)`
- This variable contains: `'production'`, `'staging'`, or `'local'`

### Test Implementation (`lib/lib_call_runtests.py`)
- Both functions create command: `[uv_path, 'run', '--no-active', run_tests.py]`
- Execute via `subprocess.run()` with project directory as cwd
- Return success/failure status with output

## Proposed Changes

### 1. Update Function Signatures to Accept environment_type

#### In `auto_updater.py` (Line 129):
```python
## ::: initial tests :::
run_initial_tests(uv_path, project_path, project_email_addresses, environment_type)  # Pass environment_type
```

#### In `auto_updater.py` (Line 152):
```python
## run post-update tests ------------------------------------
followup_tests_problems: None | str = None
followup_tests_problems = run_followup_tests(uv_path, project_path, environment_type)  # Pass environment_type
```

### 2. Modify Test Functions in `lib/lib_call_runtests.py`

#### Update `run_initial_tests()` signature and logic:
```python
def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[tuple[str, str]], environment_type: str) -> None:
    """
    Run initial tests to ensure that the script can run.
    Skips tests on production servers (environment_type == 'production').
    """
    log.info('::: running initial tests ----------')
    
    ## Skip tests on production
    if environment_type == 'production':
        log.info('Production environment detected - skipping initial tests')
        return
    
    ## prep the command ---------------------------------------------
    command: list[str] = make_run_tests_command(project_path, uv_path)
    ## [Rest of existing implementation...]
```

#### Update `run_followup_tests()` signature and logic:
```python
def run_followup_tests(uv_path: Path, project_path: Path, environment_type: str) -> None | str:
    """
    Runs followup tests on the updated venv.
    Skips tests on production servers (environment_type == 'production').
    """
    log.info('::: running followup tests ----------')
    
    ## Skip tests on production
    if environment_type == 'production':
        log.info('Production environment detected - skipping followup tests')
        return None
    
    ## prep the command ---------------------------------------------
    command: list[str] = make_run_tests_command(project_path, uv_path)
    ## [Rest of existing implementation...]
```

### 3. Update Rollback Logic (Line 172 in `auto_updater.py`)
When calling `run_followup_tests()` during rollback verification:
```python
## 3. Re-run tests to verify restoration worked
verification_result = run_followup_tests(uv_path, project_path, environment_type)  # Pass environment_type
```

## Implementation Steps

1. **Update function calls in `auto_updater.py`**
   - Pass `environment_type` to `run_initial_tests()` at line 129
   - Pass `environment_type` to `run_followup_tests()` at line 152
   - Pass `environment_type` to `run_followup_tests()` at line 172 (rollback verification)

2. **Update test runner function signatures in `lib/lib_call_runtests.py`**
   - Add production server check at the beginning of both test functions
   - Log when tests are skipped due to production environment

3. **Test the implementation**
   - Test on non-production server (hostname not starting with 'p')
   - Test on production server (hostname starting with 'p')
   - Verify logging output is clear and informative

## Considerations

### Benefits
- Prevents test failures on production servers where test environments may not be configured
- Reduces risk of production disruption from test execution
- Maintains update capability on production servers

### Trade-offs
- No validation that updates work correctly on production
- Relies on hostname convention (servers starting with 'p')
- May mask actual issues that tests would catch

### Alternative Approaches Considered
1. **Environment variable approach**: Check for `SKIP_TESTS=true` environment variable
   - Pro: More explicit control
   - Con: Requires environment configuration on each server

2. **Configuration file approach**: Add skip_tests setting to project configuration
   - Pro: Per-project control
   - Con: More complex, requires config file management

3. **Command-line flag approach**: Add `--skip-tests` flag to auto_updater.py
   - Pro: Explicit control per invocation
   - Con: Requires changes to calling scripts

## Testing Strategy

### Unit Tests
Add tests in `tests/test_*.py`:
1. Test `is_production_server()` with mocked hostnames
2. Test that `run_initial_tests()` skips when on production
3. Test that `run_followup_tests()` skips when on production

### Integration Testing
1. Run on development server (hostname not starting with 'p')
   - Verify tests execute normally
   - Verify proper logging

2. Run on staging/production server (hostname starting with 'p')
   - Verify tests are skipped
   - Verify update process continues
   - Verify proper logging indicates skipped tests

## Rollback Plan
If issues arise:
1. Remove production server checks from test functions
2. Revert to original test execution behavior
3. Document any issues encountered for future reference

## Future Enhancements
1. Add configuration option to override production detection
2. Add metrics/monitoring for skipped tests
3. Consider running a subset of "safe" tests on production
4. Add email notification when tests are skipped on production

## Documentation Updates
1. Update README.md to document production server behavior
2. Add inline comments explaining the production detection logic
3. Update AGENTS.md if needed for coding standards

---

*Note: This plan intentionally skips tests on production servers to avoid potential disruptions. The trade-off is accepted in favor of operational stability.*
