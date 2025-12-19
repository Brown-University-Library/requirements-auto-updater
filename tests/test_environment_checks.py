"""Tests for environment checks in `lib_environment_checker`."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lib import lib_environment_checker

## not needed because send_email is mocked
# @contextmanager
# def start_debugging_smtp_server() -> None:
#     """
#     Starts a debugging SMTP server for the duration of the context.
#     Called by test_validate_project_path_missing_raises()
#     """
#     command = 'uv run --python 3.12 --with aiosmtpd -m aiosmtpd -n -c aiosmtpd.handlers.Debugging --listen localhost:1026'
#     process = subprocess.Popen(
#         shlex.split(command),
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#     )
#     try:
#         time.sleep(0.5)
#         yield
#     finally:
#         process.terminate()
#         try:
#             process.wait(timeout=5)
#         except subprocess.TimeoutExpired:
#             process.kill()


class TestEnvironmentChecks(unittest.TestCase):
    """Covers the environmental validation helpers."""

    def test_validate_project_path_ok(self) -> None:
        """
        Checks legit path.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            try:
                self.assertIsNone(lib_environment_checker.validate_project_path(project_path))
            except Exception as exc:
                self.fail(f'Unexpected exception raised: {exc!r}')

    # def test_validate_project_path_missing_raises(self) -> None:
    #     """
    #     Checks bad path.
    #     """
    #     with TemporaryDirectory() as temp_dir:
    #         missing_path = Path(temp_dir) / 'missing'
    #         with start_debugging_smtp_server():
    #             with self.assertRaises(Exception) as context:
    #                 self.assertIsInstance(context, unittest.case._AssertRaisesContext)
    #                 lib_environment_checker.validate_project_path(missing_path)
    #                 ## note to self -- no code will run in the `with` after the failure, which is why the subsequent assertion must be out-dented.
    #             self.assertIn('Error: The provided project_path', str(context.exception))

    def test_validate_project_path_missing_raises(self):
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / 'missing'
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.validate_project_path(missing_path)
            self.assertIn('Error: The provided project_path', str(ctx.exception))
            mock_send.assert_called_once()  # verifies that the email attempt was made


if __name__ == '__main__':
    unittest.main()
