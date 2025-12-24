"""
Runs unittests for this repository.

Usage examples:
    uv run ./run_tests.py --help
    (all) uv run ./run_tests.py -v
    (file) uv run ./run_tests.py -v tests.test_environment_checks
    (class) uv run ./run_tests.py -v tests.test_environment_checks.TestEnvironmentChecks
    (method) uv run ./run_tests.py -v tests.test_environment_checks.TestEnvironmentChecks.test_check_branch_non_main_raises
"""

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

## set settings as early as possible --------------------------------
is_running_on_github: bool = os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'
if is_running_on_github:
    ## what should go here?
    pass
else:
    this_file_path = Path(__file__).resolve()
    stuff_dir = this_file_path.parent.parent
    dotenv_path = stuff_dir / '.env'
    assert dotenv_path.exists(), f'file does not exist, ``{dotenv_path}``'
    load_dotenv(find_dotenv(str(dotenv_path), raise_error_if_not_found=True), override=True)


import argparse
import sys
import unittest


def main() -> None:
    """
    Discover and run unittests for this repository.
    - Uses standard library unittest
    - Discovers tests under tests/ with pattern "test*.py"
    - Sets top-level directory to the repository root so `lib/` is importable
    """
    ## set up argparser ---------------------------------------------
    parser = argparse.ArgumentParser(description='Run repository unittests')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Increase verbosity (equivalent to unittest verbosity=2)',
    )
    parser.add_argument(
        'targets',
        nargs='*',
        help=(
            'Optional dotted test targets to run, e.g. '
            '(file) `tests.test_environment_checks` or '
            '(class) `tests.test_environment_checks.TestEnvironmentChecks` or '
            '(method) `tests.test_environment_checks.TestEnvironmentChecks.test_check_branch_non_main_raises`'
        ),
    )
    ## parse args ---------------------------------------------------
    args = parser.parse_args()
    ## Ensure repository root is importable (adds 'lib/', etc) ------
    repo_root = Path(__file__).parent
    sys.path.insert(0, str(repo_root))
    ## Change working directory to repo root so relative discovery works
    os.chdir(repo_root)
    start_dir = 'tests'
    loader = unittest.TestLoader()
    if args.targets:
        ## Load explicit targets provided on the command line -------
        suite = unittest.TestSuite()
        for target in args.targets:
            suite.addTests(loader.loadTestsFromName(target))
    else:
        ## Default to discovery as before ---------------------------
        suite = loader.discover(
            start_dir=start_dir,
            pattern='test*.py',
            ## Avoid specifying top_level_dir to prevent importability check on start_dir
        )
    ## Run tests ------------------------------------------------------
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result: unittest.result.TestResult = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
