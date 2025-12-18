# Plan to get tests running

## Findings
- Project dir: `requirements-auto-updater/`
- Tests dir: `requirements-auto-updater/tests/`
  - `tests.py` (contains multiple `unittest.TestCase`s)
  - `test_uv_updater.py` (properly named for discovery)
- Library code lives under `requirements-auto-updater/lib/`.
- `tests.py` manipulates `sys.path`, but only after an initial `from lib import lib_environment_checker` import at the top. This works when the current working directory is `requirements-auto-updater/`, but fails when run from the repository root.

## Why `unittest discover` yielded zero tests
- Default discovery pattern is `test*.py`. The file `tests.py` does not match this pattern and will not be collected.
- If discovery was invoked from the repo root (e.g., `auto_updater_stuff/`), imports like `from lib import ...` inside tests will fail to import, and affected modules may be skipped/errored. Running discovery in the wrong CWD easily leads to import errors or empty collections.

## Quick ways to run tests WITHOUT changing code

1) Run discovery from the project directory with explicit settings
- Change into `requirements-auto-updater/` as your working directory and run:

```
uv run -m unittest discover -v -s tests -t . -p "test*.py"
```
- Explanation:
  - `-s tests`: start dir where tests live
  - `-t .`: top-level dir added to `sys.path` (makes `lib/` importable)
  - `-p "test*.py"`: ensures only correctly named tests are discovered (`tests.py` will be ignored)

2) Run individual test modules from the project directory
- From `requirements-auto-updater/`:

```
uv run ./tests/test_uv_updater.py -v
uv run ./tests/tests.py -v
```
- Note: `./tests/tests.py` currently assumes CWD is `requirements-auto-updater/` so `lib` is importable. Running it from the repo root will raise an import error.

3) Set `PYTHONPATH` just for the command (from any directory)
- From repo root or project dir:

```
PYTHONPATH=requirements-auto-updater uv run -m unittest discover -v -s requirements-auto-updater/tests -t requirements-auto-updater -p "test*.py"
```
- This makes `requirements-auto-updater/` resolvable so `lib` imports succeed.

## Small, optional improvements (minimal code/structure changes)

These are not to be done yet; they are recommended options if you want a smoother workflow.

- Rename `tests/tests.py` -> `tests/test_main.py` (or split its classes) so default discovery (`test*.py`) picks it up without extra flags.
- Make imports package-relative by treating the project as a package:
  - Option A: Add a top-level package name and install in editable mode with uv/pip (`uv pip install -e .`), then use imports like `from requirements_auto_updater.lib import ...`. Requires adding a package name to `pyproject.toml` and possibly an `__init__.py`.
  - Option B: Keep as a flat app, but avoid early imports before `sys.path` adjustments in `tests/tests.py` (move imports after path setup). This reduces CWD-dependence.
- Add a helper script `runtests` or a Makefile with standardized commands using `-s`, `-t`, and `-p` to avoid CWD pitfalls.

## Recommended command(s) to adopt now (no code changes)

- If running from the `requirements-auto-updater/` directory:

```
uv run -m unittest discover -v -s tests -t . -p "test*.py"
```

- If running from the repo root:

```
PYTHONPATH=requirements-auto-updater \
  uv run -m unittest discover -v \
  -s requirements-auto-updater/tests \
  -t requirements-auto-updater \
  -p "test*.py"
```

This will run `test_uv_updater.py` immediately. To include the tests in `tests.py` without renaming, run it directly for now:

```
( cd requirements-auto-updater && uv run ./tests/tests.py -v )
```

## Next steps (after your go-ahead)
- Rename `tests.py` to `test_main.py` so it is included by discovery.
- (Optional) Simplify imports to be package-based or defer imports until after path adjustments to make test execution independent of CWD.
- Add a simple `make test` or `uv run -m unittest ...` task to README for a one-liner workflow.
