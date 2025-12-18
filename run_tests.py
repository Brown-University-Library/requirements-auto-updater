from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path


def main() -> None:
    """Discover and run unittests for this repository.

    - Uses standard library unittest (per AGENTS.md)
    - Discovers tests under tests/ with pattern "test*.py"
    - Sets top-level directory to the repository root so `lib/` is importable
    """
    parser = argparse.ArgumentParser(description='Run repository unittests')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Increase verbosity (equivalent to unittest verbosity=2)',
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent
    # Ensure repository root is importable (adds 'lib/' and others)
    sys.path.insert(0, str(repo_root))
    # Change working directory to repo root so relative discovery works
    os.chdir(repo_root)
    start_dir = 'tests'

    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=start_dir,
        pattern='test*.py',
        # Avoid specifying top_level_dir to prevent importability check on start_dir
    )

    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
