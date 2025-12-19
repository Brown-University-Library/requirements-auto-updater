"""
Tests for environment checks in `lib_environment_checker`.
"""

import logging
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lib import lib_environment_checker

## set up logging ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
)
log = logging.getLogger(__name__)


class TestEnvironmentChecks(unittest.TestCase):
    """
    Checks the environmental-validation helpers.
    """

    ## project path -------------------------------------------------

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

    def test_validate_project_path_missing_raises(self):
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / 'missing'
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.validate_project_path(missing_path)
            self.assertIn('Error: The provided project_path', str(ctx.exception))
            mock_send.assert_called_once()  # verifies that the email attempt was made

    ## email addresses ----------------------------------------------

    def test_determine_project_email_addresses_ok(self) -> None:
        """
        Checks ADMINS_JSON from parent .env and returned list of (name, email) tuples.
        """
        original_cwd = os.getcwd()
        try:
            with TemporaryDirectory() as parent_dir:
                parent_path = Path(parent_dir)
                log.debug(f'parent_path: ``{parent_path}``')
                project_path = parent_path / 'proj'
                project_path.mkdir(parents=True, exist_ok=True)

                # create parent .env
                env_content = 'ADMINS_JSON=\'[["Project Admin", "project_admin@example.com"]]\'\n'
                (parent_path / '.env').write_text(env_content, encoding='utf-8')

                # chdir into project directory to mirror production behavior
                os.chdir(project_path)

                result = lib_environment_checker.determine_project_email_addresses(project_path)
                self.assertEqual(result, [('Project Admin', 'project_admin@example.com')])
        finally:
            os.chdir(original_cwd)

    def test_determine_project_email_addresses_missing_env_raises(self) -> None:
        """
        Checks problem handling.
        """
        original_cwd = os.getcwd()
        try:
            with TemporaryDirectory() as parent_dir:
                parent_path = Path(parent_dir)
                project_path = parent_path / 'proj'
                project_path.mkdir(parents=True, exist_ok=True)

                # intentionally do NOT create parent .env
                os.chdir(project_path)

                with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                    with self.assertRaises(Exception):
                        lib_environment_checker.determine_project_email_addresses(project_path)
                    mock_send.assert_called_once()
        finally:
            os.chdir(original_cwd)


if __name__ == '__main__':
    unittest.main()


## old code, for reference ------------------------------------------

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
