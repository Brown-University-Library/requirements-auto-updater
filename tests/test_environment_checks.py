"""
Tests for environment checks in `lib_environment_checker`.
"""

import grp
import logging
import os
import shutil
import stat
import subprocess
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

    ## project path checks ------------------------------------------

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

    ## email address checks -----------------------------------------

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
                ## create parent .env -----------
                env_content = 'ADMINS_JSON=\'[["Project Admin", "project_admin@example.com"]]\'\n'
                (parent_path / '.env').write_text(env_content, encoding='utf-8')
                ## chdir into project directory to mirror production behavior
                os.chdir(project_path)
                ## call function ----------------
                result = lib_environment_checker.determine_project_email_addresses(project_path)
                ## assert -----------------------
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
                ## intentionally do NOT create parent .env
                os.chdir(project_path)
                ## call function ----------------
                with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                    with self.assertRaises(Exception):
                        lib_environment_checker.determine_project_email_addresses(project_path)
                    mock_send.assert_called_once()
        finally:
            os.chdir(original_cwd)

    ## branch checks ------------------------------------------------

    def test_check_branch_main_ok(self) -> None:
        """
        Checks main branch -- passes without email or exception.
        """
        with TemporaryDirectory() as temp_dir:
            ## setup dummy git directory --------
            project_path = Path(temp_dir)
            git_dir = project_path / '.git'
            git_dir.mkdir(parents=True, exist_ok=True)
            ## create HEAD file -----------------
            head_path = git_dir / 'HEAD'
            head_path.write_text('ref: refs/heads/main', encoding='utf-8')
            ## call function ----------------
            project_email_addresses = [('Admin', 'admin@example.com')]
            try:
                with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                    self.assertIsNone(lib_environment_checker.check_branch(project_path, project_email_addresses))
                    mock_send.assert_not_called()
            except Exception as exc:
                self.fail(f'Unexpected exception raised: {exc!r}')

    def test_check_branch_non_main_raises(self) -> None:
        """
        Checks non-main branch -- raises and triggers email.
        """
        with TemporaryDirectory() as temp_dir:
            ## setup dummy git directory --------
            project_path = Path(temp_dir)
            git_dir = project_path / '.git'
            git_dir.mkdir(parents=True, exist_ok=True)
            head_path = git_dir / 'HEAD'
            head_path.write_text('ref: refs/heads/feature/test', encoding='utf-8')
            ## call function ----------------
            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.check_branch(project_path, project_email_addresses)
                self.assertIn('Error: Project is on branch', str(ctx.exception))
                mock_send.assert_called_once()

    ## git status checks ---------------------------------------------
    """
    These actually use git, since the function being tested actually uses git.
    """

    @unittest.skipUnless(shutil.which('git'), 'git is required for git-status tests')
    def test_check_git_status_clean_ok(self) -> None:
        """
        Checks clean git status -- passes without email or exception.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            ## initialize git repo
            subprocess.check_call(['git', 'init'], cwd=project_path)
            subprocess.check_call(['git', 'config', 'user.name', 'Test User'], cwd=project_path)
            subprocess.check_call(['git', 'config', 'user.email', 'test@example.com'], cwd=project_path)
            ## create a tracked file and commit
            (project_path / 'README.md').write_text('# Test Repo\n', encoding='utf-8')
            subprocess.check_call(['git', 'add', 'README.md'], cwd=project_path)
            subprocess.check_call(['git', 'commit', '-m', 'init'], cwd=project_path)
            project_email_addresses = [('Admin', 'admin@example.com')]
            try:
                with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                    self.assertIsNone(lib_environment_checker.check_git_status(project_path, project_email_addresses))
                    mock_send.assert_not_called()
            except Exception as exc:
                self.fail(f'Unexpected exception raised: {exc!r}')

    @unittest.skipUnless(shutil.which('git'), 'git is required for git-status tests')
    def test_check_git_status_dirty_raises(self) -> None:
        """
        Checks dirty git status -- raises and triggers email.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            ## initialize git repo
            subprocess.check_call(['git', 'init'], cwd=project_path)
            subprocess.check_call(['git', 'config', 'user.name', 'Test User'], cwd=project_path)
            subprocess.check_call(['git', 'config', 'user.email', 'test@example.com'], cwd=project_path)
            ## create a tracked file and commit
            test_file = project_path / 'README.md'
            test_file.write_text('# Test Repo\n', encoding='utf-8')
            subprocess.check_call(['git', 'add', 'README.md'], cwd=project_path)
            subprocess.check_call(['git', 'commit', '-m', 'init'], cwd=project_path)
            ## make the repo dirty
            test_file.write_text('# Test Repo\nmodified\n', encoding='utf-8')
            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.check_git_status(project_path, project_email_addresses)
                self.assertIn('Error: git-status check failed.', str(ctx.exception))
                mock_send.assert_called_once()

    ## environment-type checks ---------------------------------------

    def test_determine_environment_type_valid_value(self) -> None:
        """
        Checks environment-type mapping from hostname with valid pyproject.toml.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            ## write a minimal, valid pyproject.toml with dependency-groups
            pyproject_content = """
            [project]
            name = "example"
            version = "0.0.0"

            [dependency-groups]
            staging = ["pkgA>=1.0"]
            production = ["pkgB>=1.0"]
            """
            (project_path / 'pyproject.toml').write_text(pyproject_content.strip() + '\n', encoding='utf-8')
            project_email_addresses = [('Admin', 'admin@example.com')]

            cases = [
                ('dev-ci-01', 'staging'),
                ('qa-host', 'staging'),
                ('prod-01', 'production'),
                ('laptop', 'local'),
            ]
            for hostname, expected in cases:
                with self.subTest(hostname=hostname, expected=expected):
                    with patch('lib.lib_environment_checker.subprocess.check_output', return_value=hostname + '\n'):
                        with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                            result = lib_environment_checker.determine_environment_type(
                                project_path, project_email_addresses
                            )
                            self.assertEqual(expected, result)
                            mock_send.assert_not_called()

    def test_determine_environment_type_missing_pyproject_raises(self) -> None:
        """
        Checks error when pyproject.toml is missing.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.determine_environment_type(project_path, project_email_addresses)
                self.assertIn('Error: Missing pyproject.toml', str(ctx.exception))
                mock_send.assert_called_once()

    def test_determine_environment_type_missing_dependency_groups_raises(self) -> None:
        """
        Checks error when `[dependency-groups]` is missing.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            ## write pyproject.toml without dependency-groups
            pyproject_content = """
            [project]
            name = "example"
            version = "0.0.0"
            """
            (project_path / 'pyproject.toml').write_text(pyproject_content.strip() + '\n', encoding='utf-8')
            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.determine_environment_type(project_path, project_email_addresses)
                self.assertIn('`[dependency-groups]` section missing', str(ctx.exception))
                mock_send.assert_called_once()

    def test_determine_environment_type_dependency_groups_wrong_type_raises(self) -> None:
        """
        Checks error when `[dependency-groups]` is not a table (treated as missing).
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            # write pyproject.toml with dependency-groups wrong type
            pyproject_content = """
            [project]
            name = "example"
            version = "0.0.0"

            dependency-groups = "oops"
            """
            (project_path / 'pyproject.toml').write_text(pyproject_content.strip() + '\n', encoding='utf-8')
            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.determine_environment_type(project_path, project_email_addresses)
                self.assertIn('`[dependency-groups]` section missing', str(ctx.exception))
                mock_send.assert_called_once()

    def test_determine_environment_type_missing_required_keys_raises(self) -> None:
        """
        Checks error when required keys in `[dependency-groups]` are missing.
        """
        ## case A: missing production
        with TemporaryDirectory() as temp_dir_a:
            project_path_a = Path(temp_dir_a)
            pyproject_content_a = """
            [project]
            name = "example"
            version = "0.0.0"

            [dependency-groups]
            staging = ["pkgA>=1.0"]
            """
            (project_path_a / 'pyproject.toml').write_text(pyproject_content_a.strip() + '\n', encoding='utf-8')
            pea = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send_a:
                with self.assertRaises(Exception) as ctx_a:
                    lib_environment_checker.determine_environment_type(project_path_a, pea)
                self.assertIn('missing required key(s): production', str(ctx_a.exception))
                mock_send_a.assert_called_once()

        ## case B: missing staging
        with TemporaryDirectory() as temp_dir_b:
            project_path_b = Path(temp_dir_b)
            pyproject_content_b = """
            [project]
            name = "example"
            version = "0.0.0"

            [dependency-groups]
            production = ["pkgB>=1.0"]
            """
            (project_path_b / 'pyproject.toml').write_text(pyproject_content_b.strip() + '\n', encoding='utf-8')
            peb = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send_b:
                with self.assertRaises(Exception) as ctx_b:
                    lib_environment_checker.determine_environment_type(project_path_b, peb)
                self.assertIn('missing required key(s): staging', str(ctx_b.exception))
                mock_send_b.assert_called_once()

    ## uv-path checks -----------------------------------------------

    def test_validate_uv_path_ok(self) -> None:
        """
        Checks legit uv path.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            uv_path = project_path / 'uv'
            uv_path.write_text('#!/bin/sh\n', encoding='utf-8')  # create a dummy file
            try:
                self.assertIsNone(lib_environment_checker.validate_uv_path(uv_path, project_path))
            except Exception as exc:
                self.fail(f'Unexpected exception raised: {exc!r}')

    def test_validate_uv_path_missing_raises(self) -> None:
        """
        Checks missing uv path triggers email and raises.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            missing_uv = project_path / 'nope-uv'
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.validate_uv_path(missing_uv, project_path)
                self.assertIn('Error: The provided uv_path', str(ctx.exception))
                mock_send.assert_called_once()

    ## group-determination checks ------------------------------------

    def test_determine_group_ok(self) -> None:
        """
        Checks group inference from a directory with at least one file.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            ## create a file so ls -l returns entries with a group
            sample_file = project_path / 'example.txt'
            sample_file.write_text('data', encoding='utf-8')

            ## compute expected group via grp and the file's gid
            expected_group = grp.getgrgid(os.stat(sample_file).st_gid).gr_name

            project_email_addresses = [('Admin', 'admin@example.com')]
            try:
                with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                    result = lib_environment_checker.determine_group(project_path, project_email_addresses)
                    self.assertEqual(expected_group, result)
                    mock_send.assert_not_called()
            except Exception as exc:
                self.fail(f'Unexpected exception raised: {exc!r}')

    def test_determine_group_invalid_raises(self) -> None:
        """
        Checks error on empty directory where no group can be inferred.
        """
        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            ## leave directory empty so `ls -l` yields no file entries
            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.determine_group(project_path, project_email_addresses)
                self.assertIn('Error inferring group:', str(ctx.exception))
                mock_send.assert_called_once()

    ## group and permissions checks ----------------------------------

    def test_check_group_and_permissions_ok(self) -> None:
        """
        Checks that group and permissions validation passes when everything is group-writable and owned by expected group.
        """
        with TemporaryDirectory() as parent_dir:
            parent_path = Path(parent_dir)
            project_path = parent_path / 'proj'
            project_path.mkdir(parents=True, exist_ok=True)

            ## set up .venv with a file
            venv_dir = project_path / '.venv'
            venv_dir.mkdir(parents=True, exist_ok=True)
            venv_file = venv_dir / 'file.txt'
            venv_file.write_text('content', encoding='utf-8')

            ## make group-writable on dir and file
            venv_dir.chmod(venv_dir.stat().st_mode | stat.S_IWGRP)
            venv_file.chmod(venv_file.stat().st_mode | stat.S_IWGRP)

            ## create uv.lock.bak in parent of project_path and make group-writable
            uv_bak = parent_path / 'uv.lock.bak'
            uv_bak.write_text('backup', encoding='utf-8')
            uv_bak.chmod(uv_bak.stat().st_mode | stat.S_IWGRP)

            ## determine expected_group from one of the files
            expected_group = grp.getgrgid(os.stat(venv_file).st_gid).gr_name

            project_email_addresses = [('Admin', 'admin@example.com')]
            try:
                with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                    self.assertIsNone(
                        lib_environment_checker.check_group_and_permissions(
                            project_path, expected_group, project_email_addresses
                        )
                    )
                    mock_send.assert_not_called()
            except Exception as exc:
                self.fail(f'Unexpected exception raised: {exc!r}')

    def test_check_group_and_permissions_perm_issue_raises(self) -> None:
        """
        Checks that missing group-write on a .venv file triggers an error and email.
        """
        with TemporaryDirectory() as parent_dir:
            parent_path = Path(parent_dir)
            project_path = parent_path / 'proj'
            project_path.mkdir(parents=True, exist_ok=True)

            ## set up .venv with two files
            venv_dir = project_path / '.venv'
            venv_dir.mkdir(parents=True, exist_ok=True)
            good_file = venv_dir / 'good.txt'
            bad_file = venv_dir / 'bad.txt'
            good_file.write_text('ok', encoding='utf-8')
            bad_file.write_text('not-ok', encoding='utf-8')

            ## make group-writable on dir and good file
            venv_dir.chmod(venv_dir.stat().st_mode | stat.S_IWGRP)
            good_file.chmod(good_file.stat().st_mode | stat.S_IWGRP)

            ## ensure bad_file is NOT group-writable
            bad_file.chmod(bad_file.stat().st_mode & ~stat.S_IWGRP)

            ## create uv.lock.bak in parent and make group-writable
            uv_bak = parent_path / 'uv.lock.bak'
            uv_bak.write_text('backup', encoding='utf-8')
            uv_bak.chmod(uv_bak.stat().st_mode | stat.S_IWGRP)

            ## expected group from a file
            expected_group = grp.getgrgid(os.stat(good_file).st_gid).gr_name

            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.check_group_and_permissions(
                        project_path, expected_group, project_email_addresses
                    )
                self.assertIn('Error: Group/Permissions check failed.', str(ctx.exception))
                mock_send.assert_called_once()

    def test_check_group_and_permissions_wrong_group_raises(self) -> None:
        """
        Checks that mismatched group ownership triggers an error and email.
        """
        with TemporaryDirectory() as parent_dir:
            parent_path = Path(parent_dir)
            project_path = parent_path / 'proj'
            project_path.mkdir(parents=True, exist_ok=True)

            ## set up .venv with a file
            venv_dir = project_path / '.venv'
            venv_dir.mkdir(parents=True, exist_ok=True)
            vfile = venv_dir / 'file.txt'
            vfile.write_text('content', encoding='utf-8')

            ## ensure group-writable so only group mismatch causes failure
            venv_dir.chmod(venv_dir.stat().st_mode | stat.S_IWGRP)
            vfile.chmod(vfile.stat().st_mode | stat.S_IWGRP)

            ## create uv.lock.bak in parent and make group-writable
            uv_bak = parent_path / 'uv.lock.bak'
            uv_bak.write_text('backup', encoding='utf-8')
            uv_bak.chmod(uv_bak.stat().st_mode | stat.S_IWGRP)

            ## pick a wrong expected group (different from actual)
            actual_group = grp.getgrgid(os.stat(vfile).st_gid).gr_name
            wrong_group = actual_group + '_not'

            project_email_addresses = [('Admin', 'admin@example.com')]
            with patch('lib.lib_environment_checker.Emailer.send_email', return_value=None) as mock_send:
                with self.assertRaises(Exception) as ctx:
                    lib_environment_checker.check_group_and_permissions(project_path, wrong_group, project_email_addresses)
                self.assertIn('Error: Group/Permissions check failed.', str(ctx.exception))
                mock_send.assert_called_once()


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
