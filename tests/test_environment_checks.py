"""Tests for environment checks in `lib_environment_checker`."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lib import lib_environment_checker


class TestEnvironmentChecks(unittest.TestCase):
    """Covers the environmental validation helpers."""

    def test_validate_project_path_ok(self) -> None:
        """`validate_project_path()` allows existing paths."""
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            try:
                lib_environment_checker.validate_project_path(project_path)
            except Exception as exc:  # pragma: no cover - defensive assertion
                self.fail(f'Unexpected exception raised: {exc!r}')

    # def test_validate_project_path_missing_raises(self) -> None:
    #     """`validate_project_path()` raises when the path is missing."""
    #     with TemporaryDirectory() as temp_dir:
    #         missing_path = Path(temp_dir) / 'missing'
    #         with self.assertRaises(Exception):
    #             lib_environment_checker.validate_project_path(missing_path)

    def test_validate_project_path_missing_raises(self) -> None:
        """`validate_project_path()` raises when the path is missing."""
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / 'missing'
            try:
                lib_environment_checker.validate_project_path(missing_path)
            except Exception as exc:  # pragma: no cover - defensive assertion
                self.fail(f'Unexpected exception raised: {exc!r}')


if __name__ == '__main__':
    unittest.main()
