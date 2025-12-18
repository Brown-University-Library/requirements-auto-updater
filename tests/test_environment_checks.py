"""Tests for environment checks in `lib_environment_checker`."""

import shlex
import subprocess
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from lib import lib_environment_checker


@contextmanager
def start_debugging_smtp_server() -> None:
    """Start a debugging SMTP server for the duration of the context."""
    command = 'uv run --python 3.12 --with aiosmtpd -m aiosmtpd -n -c aiosmtpd.handlers.Debugging --listen localhost:1026'
    process = subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.5)
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


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

    def test_validate_project_path_missing_raises(self) -> None:
        """`validate_project_path()` raises when the path is missing."""
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / 'missing'
            with start_debugging_smtp_server():
                with self.assertRaises(Exception) as context:
                    self.assertIsInstance(context, unittest.case._AssertRaisesContext)
                    lib_environment_checker.validate_project_path(missing_path)
        self.assertIn('Error: The provided project_path', str(context.exception))


if __name__ == '__main__':
    unittest.main()
