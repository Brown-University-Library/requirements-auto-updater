# Plan: Implement Python Version Validation

## Overview
Implement the Python version check referenced in README.md line 40 and identified as missing in FLOW_ANALYSIS.md. This validation should ensure that target projects have a Python version specification in their `pyproject.toml` file.

---

## Context

### Current State
- **Location in Flow**: The check should occur in the "initial checks" phase of `manage_update()` in `auto_updater.py`, after `check_git_status()` and before `determine_environment_type()`
- **README Reference**: Line 40 states "ensures a python version is listed -- TODO"
- **Impact**: Low severity - projects will likely fail early if Python version is misconfigured, but explicit validation provides clearer error messages
- **Pattern to Follow**: Existing validation functions in `lib/lib_environment_checker.py`

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
def validate_python_version(project_path: Path, project_email_addresses: list[tuple[str, str]]) -> None
```

**Implementation Details:**
- **Location**: Add after `check_git_status()` function (around line 154)
- **Logic**:
  1. Log `::: validating python version ----------`
  2. Read `pyproject.toml` from `project_path`
  3. Parse TOML using `tomllib` (already imported)
  4. Check for `project.requires-python` field
  5. Validate that the field exists and is a non-empty string
  6. Log success: `ok / python version specified: {version_spec}`
  7. On any failure:
     - Create error message
     - Email project admins
     - Raise exception

**Error Conditions:**
- `pyproject.toml` does not exist → email project admins
- `[project]` section missing → email project admins
- `requires-python` field missing → email project admins
- `requires-python` is empty or not a string → email project admins

**Type Hints:**
- Use Python 3.12 style type hints
- Use `Path` from `pathlib`
- Use `list[tuple[str, str]]` for email addresses (not `typing.List`)
- Return type: `None`

**Docstring Format** (per AGENTS.md):
```python
"""
Validates that the project's pyproject.toml contains a Python version specification.
If validation fails:
- Sends an email to the project admins
- Exits the script
"""
```

### 2. Integrate into `auto_updater.py`

**Location**: In `manage_update()` function, after line 115 (`check_git_status()`)

**Code Addition:**
```python
## validate python version -------------------------------------
lib_environment_checker.validate_python_version(project_path, project_email_addresses)
```

**Rationale for Placement:**
- After `check_git_status()` because we need a clean repo
- Before `determine_environment_type()` because that function already reads `pyproject.toml` and validates dependency-groups
- Follows the logical flow: path → emails → git state → python config → environment detection

### 3. Add Comprehensive Tests to `tests/test_environment_checks.py`

**Test Cases to Implement:**

#### 3.1 Happy Path Test
```python
def test_validate_python_version_ok(self) -> None:
    """
    Checks that validation passes with valid requires-python specification.
    """
```
- Create temp directory with `pyproject.toml`
- Include valid `requires-python` field (e.g., `">=3.12"`)
- Assert function returns None without raising
- Assert no email sent

#### 3.2 Missing pyproject.toml
```python
def test_validate_python_version_missing_pyproject_raises(self) -> None:
    """
    Checks that missing pyproject.toml triggers error and email.
    """
```
- Create temp directory without `pyproject.toml`
- Mock `Emailer.send_email`
- Assert exception raised with appropriate message
- Assert email sent once

#### 3.3 Missing [project] Section
```python
def test_validate_python_version_missing_project_section_raises(self) -> None:
    """
    Checks that missing [project] section triggers error and email.
    """
```
- Create `pyproject.toml` without `[project]` section
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 3.4 Missing requires-python Field
```python
def test_validate_python_version_missing_field_raises(self) -> None:
    """
    Checks that missing requires-python field triggers error and email.
    """
```
- Create `pyproject.toml` with `[project]` but no `requires-python`
- Mock `Emailer.send_email`
- Assert exception raised with message about missing field
- Assert email sent once

#### 3.5 Empty requires-python Value
```python
def test_validate_python_version_empty_value_raises(self) -> None:
    """
    Checks that empty requires-python value triggers error and email.
    """
```
- Create `pyproject.toml` with `requires-python = ""`
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 3.6 Invalid Type for requires-python
```python
def test_validate_python_version_wrong_type_raises(self) -> None:
    """
    Checks that non-string requires-python value triggers error and email.
    """
```
- Create `pyproject.toml` with `requires-python = 3.12` (number, not string)
- Mock `Emailer.send_email`
- Assert exception raised
- Assert email sent once

#### 3.7 Various Valid Formats
```python
def test_validate_python_version_various_formats_ok(self) -> None:
    """
    Checks that various valid requires-python formats pass validation.
    """
```
- Test multiple valid formats using `subTest`:
  - `">=3.12"`
  - `">=3.12,<3.13"`
  - `"==3.12.*"`
  - `"~=3.12.0"`
- Assert all pass without error

**Test Location**: Add after the `test_check_git_status_*` tests (around line 193)

**Test Structure** (per AGENTS.md):
- Use `unittest` framework (not pytest)
- Use `TemporaryDirectory` for file system operations
- Mock `Emailer.send_email` to avoid actual email sending
- Use descriptive docstrings starting with "Checks..."
- Follow existing test patterns in the file

### 4. Update Documentation

#### 4.1 README.md
**Line 40**: Remove the "-- TODO" suffix
```markdown
- ensures a python version is listed
```

#### 4.2 FLOW_ANALYSIS.md
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

1. **Write the validation function** in `lib/lib_environment_checker.py`
   - Follow existing patterns exactly
   - Include proper logging
   - Handle all error cases

2. **Add function call** to `auto_updater.py`
   - Insert in correct location in flow
   - Pass required parameters

3. **Write comprehensive tests** in `tests/test_environment_checks.py`
   - Cover all success and failure cases
   - Mock email sending
   - Use `TemporaryDirectory` for file operations

4. **Run tests** to verify implementation:
   ```bash
   uv run ./run_tests.py
   ```

5. **Update documentation**:
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

---

## Success Criteria

- ✅ Validation function added to `lib/lib_environment_checker.py`
- ✅ Function integrated into `auto_updater.py` flow
- ✅ All test cases implemented and passing
- ✅ Existing tests continue to pass
- ✅ Documentation updated (README.md, FLOW_ANALYSIS.md)
- ✅ Code follows AGENTS.md style guidelines
- ✅ Proper error messages and email notifications
- ✅ Logging statements added for debugging

---

## Notes

### Why This Check Matters
- Provides clear error messages early in the process
- Prevents cryptic failures later during `uv sync`
- Ensures project configuration completeness
- Aligns with project assumptions documented in README.md

### Design Decisions
1. **Validation only, no version comparison**: We only check that a Python version is specified, not that it matches the running Python version. This is appropriate because `uv` will handle version compatibility.

2. **Email project admins**: Since this is a project configuration issue (not a system/environment issue), we email project admins rather than sys admins.

3. **No format validation**: We don't validate the format of the version specifier (e.g., PEP 440 compliance) because `uv` will catch invalid formats with better error messages.

4. **Placement in flow**: Positioned early in the validation sequence but after basic git checks, allowing for early failure with clear messaging.

### Future Enhancements (Out of Scope)
- Validate that the specified Python version matches the running Python version
- Validate PEP 440 version specifier format
- Check for Python version compatibility with dependencies
