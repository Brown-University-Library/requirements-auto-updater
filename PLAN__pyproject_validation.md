# Plan: Implement pyproject.toml Validation

## Overview
Implement comprehensive `pyproject.toml` validation to consolidate and improve project configuration checks. This addresses the Python version check referenced in README.md line 40 and identified as missing in FLOW_ANALYSIS.md, while also refactoring existing dependency-groups validation from `determine_environment_type()` into a dedicated validation function.

**Scope**: This validation consolidates all `pyproject.toml` checks into a single function:
- File existence
- `[project]` section presence
- `requires-python` field validation (addresses the TODO)
- `[dependency-groups]` section validation (moved from `determine_environment_type()`)
- Required dependency group keys (`staging`, `prod`)

---

## Context

### Current State
- **Location in Flow**: The check should occur in the "initial checks" phase of `manage_update()` in `auto_updater.py`, after `check_git_status()` and before `determine_environment_type()`
- **README Reference**: Line 40 states "ensures a python version is listed -- TODO"
- **Impact**: Medium severity - consolidates scattered validation logic and provides clearer error messages earlier in the flow
- **Pattern to Follow**: Existing validation functions in `lib/lib_environment_checker.py`
- **Refactoring Required**: Move dependency-groups validation from `determine_environment_type()` (lines 162-198) into the new validation function

### Existing Validation Pattern
All environment checks in `lib_environment_checker.py` follow this pattern:
1. Log the check being performed
2. Perform validation logic
3. On failure:
   - Log the error
   - Create an `Emailer` instance
   - Send email to project admins (or sys admins for setup issues)
   - Raise an exception with descriptive message
4. On success:
   - Log success message
   - Return result (if applicable) or None

### Python Version Specification Formats
Based on `pyproject.toml` examples:
- This project uses: `requires-python = ">=3.12,<3.13"`
- PEP 621 standard field: `project.requires-python`
- Common formats:
  - `">=3.12"` (minimum version)
  - `">=3.12,<3.13"` (range)
  - `"==3.12.*"` (specific minor version)

---

## Implementation Plan

### 1. Add Validation Function to `lib/lib_environment_checker.py`

**Function Signature:**
```python
def validate_pyproject_toml(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None
```

**Implementation Details:**
- **Location**: Add after `check_git_status()` function (around line 154)
- **Logic**:
  1. Log `::: validating pyproject.toml ----------`
  2. **Check for `pyproject.toml` existence**
  3. Parse TOML using `tomllib` (already imported)
  4. **Check for `[project]` section**
  5. **Check for `project.requires-python` field** (addresses README TODO)
     - Validate that the field exists and is a non-empty string
  6. **Check for `[dependency-groups]` section** (moved from `determine_environment_type()`)
     - Validate it exists and is a dict
  7. **Check for required dependency group keys** (moved from `determine_environment_type()`)
     - Validate `staging` and `prod` keys exist
  8. Log success: `ok / pyproject.toml validated (python version: {version_spec})`
  9. On any failure:
     - Create error message
     - Email project admins
     - Raise exception

**Error Conditions:**
- `pyproject.toml` does not exist → email project admins
- `[project]` section missing → email project admins
- `requires-python` field missing → email project admins *(NEW - addresses TODO)*
- `requires-python` is empty or not a string → email project admins *(NEW - addresses TODO)*
- `[dependency-groups]` section missing → email project admins *(MOVED from determine_environment_type)*
- `[dependency-groups]` is not a dict → email project admins *(MOVED from determine_environment_type)*
- Required keys (`staging`, `prod`) missing from `[dependency-groups]` → email project admins *(MOVED from determine_environment_type)*

**Validation Scope:**
This function consolidates all `pyproject.toml` validation into a single location, checking file structure, Python version requirements, and dependency groups. This eliminates redundant file reading and creates a clear, comprehensive validation point early in the flow.

**Type Hints:**
- Use Python 3.12 style type hints
- Use `Path` from `pathlib`
- Use `list[tuple[str, str]]` for email addresses (not `typing.List`)
- Return type: `None`

**Docstring Format** (per AGENTS.md):
```python
"""
Validates the project's pyproject.toml file structure and required fields.
Checks for:
- File existence
- [project] section with requires-python field
- [dependency-groups] section with staging and prod keys
If validation fails:
- Sends an email to the project admins
- Exits the script
"""
```

### 2. Refactor `determine_environment_type()` in `lib/lib_environment_checker.py`

**Changes Required:**
- **Remove** the dependency-groups validation logic (lines 162-198)
- **Keep** only the hostname-based environment detection logic (lines 200-209)
- **Update** the function to be simpler and focused solely on determining environment type
- **Update** docstring to reflect that it no longer validates `pyproject.toml`

**Simplified Logic:**
```python
def determine_environment_type(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> str:
    """
    Infers environment type based on the system hostname.
    Returns 'local', 'staging', or 'production'.
    Note: pyproject.toml validation is handled by validate_pyproject_toml().
    """
    log.info('::: determining environment type ----------')
    hostname: str = subprocess.check_output(['hostname'], text=True).strip().lower()
    if hostname.startswith('d') or hostname.startswith('q'):
        env_type: str = 'staging'
    elif hostname.startswith('p'):
        env_type: str = 'production'
    else:
        env_type: str = 'local'
    log.info(f'ok / env_type, ``{env_type}``')
    return env_type
```

### 3. Integrate into `auto_updater.py`

**Location**: In `manage_update()` function, after line 115 (`check_git_status()`)

**Code Addition:**
```python
## validate pyproject.toml -------------------------------------
lib_environment_checker.validate_pyproject_toml(project_path, project_email_addresses)
```

**Rationale for Placement:**
- After `check_git_status()` because we need a clean repo
- Before `determine_environment_type()` because that function now relies on the validation being complete
- Consolidates all `pyproject.toml` validation in one place before any function tries to use it
- Follows the logical flow: path → emails → git state → project config validation → environment detection → system tools

### 4. Add Comprehensive Tests to `tests/test_environment_checks.py`

**Test Cases to Implement:**

#### 4.1 Happy Path Test
```python
def test_validate_pyproject_toml_ok(self) -> None:
    """
    Checks that validation passes with complete valid pyproject.toml.
    """
```
- Create temp directory with `pyproject.toml`
- Include `[project]` section with valid `requires-python` field (e.g., `">=3.12"`)
- Include `[dependency-groups]` section with `staging` and `prod` keys
- Assert function returns None without raising
- Assert no email sent

#### 4.2 Missing pyproject.toml
```python
def test_validate_pyproject_toml_missing_file_raises(self) -> None:
    """
    Checks that missing pyproject.toml triggers error and email.
    """
```
- Create temp directory without `pyproject.toml`
- Mock `Emailer.send_email`
- Assert exception raised with appropriate message
- Assert email sent once

#### 4.3 Missing [project] Section
```python
def test_validate_pyproject_toml_missing_project_section_raises(self) -> None:
    """
    Checks that missing [project] section triggers error and email.
    """
```
- Create `pyproject.toml` without `[project]` section
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 4.4 Missing requires-python Field
```python
def test_validate_pyproject_toml_missing_requires_python_raises(self) -> None:
    """
    Checks that missing requires-python field triggers error and email.
    """
```
- Create `pyproject.toml` with `[project]` and `[dependency-groups]` but no `requires-python`
- Mock `Emailer.send_email`
- Assert exception raised with message about missing field
- Assert email sent once

#### 4.5 Empty requires-python Value
```python
def test_validate_pyproject_toml_empty_requires_python_raises(self) -> None:
    """
    Checks that empty requires-python value triggers error and email.
    """
```
- Create `pyproject.toml` with `requires-python = ""`
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 4.6 Invalid Type for requires-python
```python
def test_validate_pyproject_toml_wrong_type_requires_python_raises(self) -> None:
    """
    Checks that non-string requires-python value triggers error and email.
    """
```
- Create `pyproject.toml` with `requires-python = 3.12` (number, not string)
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 4.7 Missing [dependency-groups] Section
```python
def test_validate_pyproject_toml_missing_dependency_groups_raises(self) -> None:
    """
    Checks that missing [dependency-groups] section triggers error and email.
    """
```
- Create `pyproject.toml` with `[project]` and `requires-python` but no `[dependency-groups]`
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 4.8 Invalid Type for [dependency-groups]
```python
def test_validate_pyproject_toml_wrong_type_dependency_groups_raises(self) -> None:
    """
    Checks that non-dict dependency-groups value triggers error and email.
    """
```
- Create `pyproject.toml` with `dependency-groups = "oops"`
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 4.9 Missing Required Dependency Group Keys
```python
def test_validate_pyproject_toml_missing_dependency_group_keys_raises(self) -> None:
    """
    Checks that missing required keys in [dependency-groups] triggers error and email.
    """
```
- Test two cases using `subTest`:
  - Missing `prod` key
  - Missing `staging` key
- Mock `Emailer.send_email`
- Assert exception raised with appropriate message
- Assert email sent once

#### 4.10 Various Valid Formats
```python
def test_validate_pyproject_toml_various_formats_ok(self) -> None:
    """
    Checks that various valid requires-python formats pass validation.
    """
```
- Test multiple valid formats using `subTest`:
  - `">=3.12"`
  - `">=3.12,<3.13"`
  - `"==3.12.*"`
  - `"~=3.12.0"`
- All tests include valid `[dependency-groups]` section
- Assert all pass without error

**Test Location**: Add after the `test_check_git_status_*` tests (around line 193)

**Test Structure** (per AGENTS.md):
- Use `unittest` framework (not pytest)
- Use `TemporaryDirectory` for file system operations
- Mock `Emailer.send_email` to avoid actual email sending
- Use descriptive docstrings starting with "Checks..."
- Follow existing test patterns in the file

### 5. Update Tests for `determine_environment_type()`

**Changes Required:**
The existing tests for `determine_environment_type()` in `tests/test_environment_checks.py` will need updates:

- **Keep** tests that verify hostname-based environment detection
- **Remove** or **simplify** tests that verify `pyproject.toml` validation (since that's now in `validate_pyproject_toml()`)
- Tests like `test_determine_environment_type_missing_pyproject_raises()` should be removed (now covered by `test_validate_pyproject_toml_missing_file_raises()`)
- Tests like `test_determine_environment_type_missing_dependency_groups_raises()` should be removed (now covered by new tests)
- **Keep** `test_determine_environment_type_valid_value()` but simplify it to not need to validate the full `pyproject.toml` structure

### 6. Update Documentation

#### 6.1 README.md
**Line 40**: Remove the "-- TODO" suffix
```markdown
- ensures a python version is listed
```

#### 6.2 FLOW_ANALYSIS.md
**Section "❌ 1. Python Version Validation"**: Update status to implemented
- Change ❌ to ✅
- Update **Status:** to "Implemented"
- Add implementation details

---

## Code Style Requirements (from AGENTS.md)

### Type Hints
- Use Python 3.12 type hints everywhere
- Prefer builtin generics: `list[str]`, `dict[str, int]`
- Prefer PEP 604 unions: `str | None` over `Optional[str]`
- Avoid `typing` imports unless strictly necessary

### Docstrings
- Use triple-quoted docstrings on their own lines
- Write in present tense
- Test docstrings start with "Checks..."
- Header comments in functions start with `##`

### Function Structure
- Prefer single-return functions
- No nested function definitions
- Keep logic clear and explicit

### Imports
- `tomllib` is already imported in `lib_environment_checker.py`
- No new imports needed for this feature

---

## Testing Strategy

### Manual Testing Steps
1. **Run existing tests** to ensure no regressions:
   ```bash
   uv run ./run_tests.py
   ```

2. **Test with valid project**:
   - Use a test project with proper `pyproject.toml`
   - Verify validation passes silently

3. **Test with invalid project**:
   - Create test project without `requires-python`
   - Verify appropriate error message and email

4. **Test integration**:
   - Run full `auto_updater.py` on test project
   - Verify check occurs in correct sequence

### Automated Testing
- All new tests must pass
- Existing tests must continue to pass
- Run: `uv run ./run_tests.py`

---

## Implementation Order

1. **Write the new validation function** `validate_pyproject_toml()` in `lib/lib_environment_checker.py`
   - Add after `check_git_status()` function (around line 154)
   - Follow existing patterns exactly
   - Include proper logging
   - Handle all error cases
   - Include all validation logic (file, project section, requires-python, dependency-groups)

2. **Refactor `determine_environment_type()`** in `lib/lib_environment_checker.py`
   - Remove dependency-groups validation logic (lines 162-198)
   - Keep only hostname-based environment detection
   - Update docstring
   - Simplify function significantly

3. **Add function call** to `auto_updater.py`
   - Insert in correct location in flow (after `check_git_status()`)
   - Pass required parameters
   - Replace: `## get environment-type` comment with `## validate pyproject.toml`

4. **Write comprehensive tests** for `validate_pyproject_toml()` in `tests/test_environment_checks.py`
   - Cover all success and failure cases (10 test cases)
   - Mock email sending
   - Use `TemporaryDirectory` for file operations

5. **Update tests** for `determine_environment_type()` in `tests/test_environment_checks.py`
   - Remove tests that validate `pyproject.toml` structure
   - Keep tests that verify hostname-based environment detection
   - Simplify remaining tests

6. **Run tests** to verify implementation:
   ```bash
   uv run ./run_tests.py
   ```

7. **Update documentation**:
   - Remove TODO from README.md
   - Update FLOW_ANALYSIS.md status

---

## Error Messages

### Missing pyproject.toml
```
Error: Missing pyproject.toml at `{pyproject_path}`
```

### Missing [project] Section
```
Error: `[project]` section missing from pyproject.toml
```

### Missing requires-python Field
```
Error: `requires-python` field missing from [project] section in pyproject.toml
```

### Invalid requires-python Value
```
Error: `requires-python` field in pyproject.toml is empty or invalid (must be a non-empty string)
```

### Missing [dependency-groups] Section
```
Error: `[dependency-groups]` section missing from pyproject.toml
```

### Invalid [dependency-groups] Type
```
Error: `[dependency-groups]` section in pyproject.toml must be a table/dict
```

### Missing Required Dependency Group Keys
```
Error: `[dependency-groups]` in pyproject.toml is missing required key(s): staging, prod
```

---

## Success Criteria

- ✅ New `validate_pyproject_toml()` function added to `lib/lib_environment_checker.py`
- ✅ `determine_environment_type()` refactored to remove validation logic
- ✅ Function integrated into `auto_updater.py` flow
- ✅ All new test cases implemented and passing (10 tests)
- ✅ Existing tests updated (remove redundant validation tests)
- ✅ All tests continue to pass
- ✅ Documentation updated (README.md, FLOW_ANALYSIS.md)
- ✅ Code follows AGENTS.md style guidelines
- ✅ Proper error messages and email notifications
- ✅ Logging statements added for debugging
- ✅ No duplicate validation logic across functions

---

## Notes

### Why This Check Matters
- Provides clear error messages early in the process
- Prevents cryptic failures later during `uv sync`
- Ensures project configuration completeness
- Aligns with project assumptions documented in README.md
- Serves as foundational `pyproject.toml` validation that other checks can rely on

### Design Decisions
1. **Consolidation over separation**: Rather than having validation scattered across multiple functions, all `pyproject.toml` validation is consolidated into `validate_pyproject_toml()`. This eliminates redundant file reading and provides a single point of validation.

2. **Refactoring `determine_environment_type()`**: This function previously mixed validation with environment detection. The refactored version focuses solely on hostname-based environment detection, making it simpler and more focused.

3. **Validation only, no version comparison**: We only check that a Python version is specified, not that it matches the running Python version. This is appropriate because `uv` will handle version compatibility.

4. **Email project admins**: Since this is a project configuration issue (not a system/environment issue), we email project admins rather than sys admins.

5. **No format validation**: We don't validate the format of the version specifier (e.g., PEP 440 compliance) or dependency group contents because `uv` will catch invalid formats with better error messages.

6. **Placement in flow**: Positioned early in the validation sequence but after basic git checks, allowing for early failure with clear messaging. All `pyproject.toml` validation happens before any function tries to use the file.

7. **Single file read**: By consolidating validation, we read and parse `pyproject.toml` only once during the validation phase, improving efficiency.

### Future Enhancements (Out of Scope)
- Validate that the specified Python version matches the running Python version
- Validate PEP 440 version specifier format
- Check for Python version compatibility with dependencies
