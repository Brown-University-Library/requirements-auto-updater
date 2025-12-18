# Plan to get tests running

## Findings
- Project dir: `requirements-auto-updater/`
- Tests dir: `requirements-auto-updater/tests/`
  - `test_main.py` (contains multiple `unittest.TestCase`s)
  - `test_uv_updater.py` (properly named for discovery)
- Library code lives under `requirements-auto-updater/lib/`.

### New
- `run_tests.py` exists at the project root and standardizes running tests via `uv` and stdlib `unittest`.


## Recommended command(s) to adopt now (no code changes)

- If running from the `requirements-auto-updater/` directory:

```
uv run ./run_tests.py -v
```

This will run both `test_uv_updater.py` and `test_main.py`.

## Next steps
- Add a short section to `README.md` under "How to run tests" that references `uv run ./run_tests.py -v`.
- Continue finishing tests in `tests/test_main.py` and `tests/test_uv_updater.py`.
- When stabilizing tests, consider structured assertions around any subprocess output (e.g., `lib_git_handler.run_git_pull()` capturing `stdout`). Do not change code yet; finish tests first.
- Optionally add CI (e.g., GitHub Actions) to run `uv run ./run_tests.py -v` on pushes/PRs.
