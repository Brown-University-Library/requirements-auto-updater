import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.lib_uv_updater import UvUpdater

## set up logging ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
)
log = logging.getLogger(__name__)


class TestUvUpdater(unittest.TestCase):
    def test_make_dry_run_sync_command_staging(self) -> None:
        """
        Checks that the dry-run sync command includes json output for the staging group.
        """
        updater = UvUpdater()
        command = updater.make_dry_run_sync_command(Path('/usr/local/bin/uv'), 'staging')
        self.assertEqual(
            command,
            [
                '/usr/local/bin/uv',
                'sync',
                '--no-active',
                '--upgrade',
                '--group',
                'staging',
                '--dry-run',
                '--output-format',
                'json',
            ],
        )

    def test_run_dry_run_sync_command_returns_metadata_only_classification(self) -> None:
        """
        Checks that run_dry_run_sync_command() classifies lock-only change output as metadata-only.
        """
        updater = UvUpdater()
        completed_process = subprocess.CompletedProcess(
            args=['uv', 'sync', '--dry-run'],
            returncode=0,
            stdout='{"sync":{"action":"check"},"lock":{"action":"write"},"dry_run":true}',
            stderr='',
        )
        with patch('subprocess.run', return_value=completed_process):
            result = updater.run_dry_run_sync_command(['uv', 'sync', '--dry-run'], Path('/tmp/project'))
        self.assertTrue(result['ok'])
        self.assertIsNotNone(result['classification'])
        self.assertTrue(result['classification']['is_exclude_newer_only'])

    def test_compare_uv_lock_files_happy_path_returns_diff(self) -> None:
        """
        Checks that compare_uv_lock_files() returns a dict indicating changes with unified diff text when files differ.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            uv_lock_path = tmp_path / 'uv.lock'
            log.debug(f'uv_lock_path: ``{uv_lock_path}``')
            uv_lock_backup_path = tmp_path / 'uv.lock.bak'
            log.debug(f'uv_lock_backup_path: ``{uv_lock_backup_path}``')

            ## previous (backup) content
            uv_lock_backup_path.write_text('version = 1\n[package]\nfoo = "1.0.0"\n')

            ## current content (changed)
            uv_lock_path.write_text('version = 1\n[package]\nfoo = "1.1.0"\nbar = "0.2.0"\n')

            result = updater.compare_uv_lock_files(uv_lock_path, uv_lock_backup_path)

            self.assertIsInstance(result, dict)
            self.assertIn('changes', result)
            self.assertIn('diff', result)
            self.assertTrue(result['changes'])
            diff_text: str = result['diff']
            self.assertNotEqual(diff_text.strip(), '')
            ## Expect unified diff headers to reference the two files
            self.assertIn(str(uv_lock_backup_path), diff_text)
            self.assertIn(str(uv_lock_path), diff_text)
            ## Expect to see changed line indicators
            self.assertIn('+bar = "0.2.0"', diff_text)
            self.assertIn('-foo = "1.0.0"', diff_text)
            self.assertIn('+foo = "1.1.0"', diff_text)

    def test_compare_uv_lock_files_failure_returns_empty_result(self) -> None:
        """
        Checks that compare_uv_lock_files() gracefully returns a dict with no changes and empty diff on exception (e.g., missing file).
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            uv_lock_path = tmp_path / 'uv.lock'
            # write only the current file; provide a non-existent backup path
            uv_lock_path.write_text('content\n')
            missing_backup = tmp_path / 'does_not_exist.lock.bak'

            result = updater.compare_uv_lock_files(uv_lock_path, missing_backup)
            self.assertIsInstance(result, dict)
            self.assertFalse(result.get('changes', True))
            self.assertEqual(result.get('diff', None), '')

    def test_manage_sync_failure_sends_email_and_raises(self) -> None:
        """
        Checks that manage_sync() emails project admins and raises on sync failure.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            project_path = tmp_path / 'project'
            project_path.mkdir(parents=True, exist_ok=True)
            uv_lock_path = project_path / 'uv.lock'
            uv_lock_path.write_text('version = 1\n', encoding='utf-8')
            uv_lock_backup_path = project_path.parent / 'uv.lock.bak'
            uv_lock_backup_path.write_text('version = 1\n', encoding='utf-8')
            sync_failure = subprocess.CompletedProcess(
                args=['uv', 'sync'],
                returncode=2,
                stdout='',
                stderr='sync failed',
            )
            sync_revert = subprocess.CompletedProcess(
                args=['uv', 'sync', '--frozen'],
                returncode=0,
                stdout='',
                stderr='',
            )
            run_tests_result = subprocess.CompletedProcess(
                args=['uv', 'run', 'run_tests.py'],
                returncode=0,
                stdout='',
                stderr='',
            )
            project_email_addresses = [('Admin', 'admin@example.com')]
            with (
                patch('subprocess.run', side_effect=[sync_failure, sync_revert, run_tests_result]),
                patch('lib.lib_emailer.Emailer.send_email', return_value=None) as mock_send,
            ):
                with self.assertRaises(Exception):
                    updater.manage_sync(
                        Path('uv'),
                        project_path,
                        'staging',
                        project_email_addresses,
                    )
                mock_send.assert_called_once()

    def test_manage_sync_failure_skips_tests_on_production(self) -> None:
        """
        Checks that manage_sync() skips rollback tests on production sync failure.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            project_path = tmp_path / 'project'
            project_path.mkdir(parents=True, exist_ok=True)
            uv_lock_path = project_path / 'uv.lock'
            uv_lock_path.write_text('version = 1\n', encoding='utf-8')
            uv_lock_backup_path = project_path.parent / 'uv.lock.bak'
            uv_lock_backup_path.write_text('version = 1\n', encoding='utf-8')
            sync_failure = subprocess.CompletedProcess(
                args=['uv', 'sync'],
                returncode=2,
                stdout='',
                stderr='sync failed',
            )
            sync_revert = subprocess.CompletedProcess(
                args=['uv', 'sync', '--frozen'],
                returncode=0,
                stdout='',
                stderr='',
            )
            project_email_addresses = [('Admin', 'admin@example.com')]
            with (
                patch('subprocess.run', side_effect=[sync_failure, sync_revert]),
                patch('lib.lib_call_runtests.run_run_tests_command') as mock_run_tests,
                patch('lib.lib_emailer.Emailer.send_email', return_value=None) as mock_send,
            ):
                with self.assertRaises(Exception):
                    updater.manage_sync(
                        Path('uv'),
                        project_path,
                        'production',
                        project_email_addresses,
                    )
                mock_run_tests.assert_not_called()
                mock_send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
