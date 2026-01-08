# Plan: Skip Tests on Production Servers

## Overview
This document outlines the plan to modify the auto-updater script to detect production servers (hostnames starting with 'p') and skip test execution on those servers while maintaining the update workflow.

## Current Test Execution Flow

### Test Points in `auto_updater.py`
1. **Initial Tests** (Line 129): `run_initial_tests(uv_path, project_path, project_email_addresses)`
   - Runs before any updates to validate environment health
   - On failure: emails admins and raises exception to halt auto-update
   
2. **Follow-up Tests** (Line 152): `run_followup_tests(uv_path, project_path)`
   - Runs after virtualenv updates
   - On failure: returns error message but continues processing (for rollback/email/permissions)

### Test Implementation (`lib/lib_call_runtests.py`)
- Both functions create command: `[uv_path, 'run', '--no-active', run_tests.py]`
- Execute via `subprocess.run()` with project directory as cwd
- Return success/failure status with output

## Proposed Changes

### 1. Add Server Detection Function
**Location**: `lib/lib_common.py` (or new `lib/lib_server_detector.py`)

```python
def is_production_server() -> bool:
    """
    Detects if the current server is a production server.
    Production servers have hostnames that start with 'p'.
    """
    import socket
    hostname = socket.gethostname().lower()
    return hostname.startswith('p')
```

**Alternative Implementation** (using platform):
```python
def is_production_server() -> bool:
    """
    Detects if the current server is a production server.
    Production servers have hostnames that start with 'p'.
    """
    import platform
    hostname = platform.node().lower()
    return hostname.startswith('p')
```

### 2. Modify Test Functions in `lib/lib_call_runtests.py`

#### Update `run_initial_tests()`
```python
def run_initial_tests(uv_path: Path, project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None:
    """
    Run initial tests to ensure that the script can run.
    Skips tests on production servers (hostname starts with 'p').
    """
    log.info('::: running initial tests ----------')
    
    ## Check if production server
    if is_production_server():
        log.info('Production server detected (hostname starts with "p") - skipping initial tests')
        return
    
    ## [Rest of existing implementation...]
```

#### Update `run_followup_tests()`
```python
def run_followup_tests(uv_path: Path, project_path: Path) -> None | str:
    """
    Runs followup tests on the updated venv.
    Skips tests on production servers (hostname starts with 'p').
    """
    log.info('::: running followup tests ----------')
    
    ## Check if production server
    if is_production_server():
        log.info('Production server detected (hostname starts with "p") - skipping followup tests')
        return None
    
    ## [Rest of existing implementation...]
```

### 3. Import Requirements
Add import at top of `lib/lib_call_runtests.py`:
```python
from lib.lib_common import is_production_server  # or from lib.lib_server_detector
```

## Implementation Steps

1. **Create server detection function**
   - Add `is_production_server()` to `lib/lib_common.py`
   - Include appropriate logging for transparency

2. **Update test runner functions**
   - Import the detection function
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
