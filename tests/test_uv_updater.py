import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.lib_uv_updater import UvUpdater


class TestUvUpdater(unittest.TestCase):
    def test_make_upgrade_dry_run_command_staging(self) -> None:
        """
        Checks that the staging dry-run sync command includes upgrade and json output flags.
        """
        updater = UvUpdater()
        command = updater.make_upgrade_dry_run_command(Path('/usr/local/bin/uv'), 'staging')
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

    def test_make_upgrade_sync_command_staging(self) -> None:
        """
        Checks that the staging sync command uses the upgrade flag.
        """
        updater = UvUpdater()
        command = updater.make_upgrade_sync_command(Path('/usr/local/bin/uv'), 'staging')
        self.assertEqual(
            command,
            ['/usr/local/bin/uv', 'sync', '--no-active', '--upgrade', '--group', 'staging'],
        )

    def test_make_locked_sync_command_production(self) -> None:
        """
        Checks that the production sync command uses --locked and the prod dependency group.
        """
        updater = UvUpdater()
        command = updater.make_locked_sync_command(Path('/usr/local/bin/uv'), 'production')
        self.assertEqual(
            command,
            ['/usr/local/bin/uv', 'sync', '--no-active', '--locked', '--group', 'prod'],
        )

    def test_make_restore_sync_command_uses_group_mapping(self) -> None:
        """
        Checks that restore sync uses the mapped prod group name instead of the environment label.
        """
        updater = UvUpdater()
        command = updater.make_restore_sync_command(Path('/usr/local/bin/uv'), 'production')
        self.assertEqual(
            command,
            ['/usr/local/bin/uv', 'sync', '--no-active', '--frozen', '--group', 'prod'],
        )
        self.assertNotIn('production', command)

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
        Checks that compare_uv_lock_files() returns unified diff text when files differ.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            uv_lock_path = tmp_path / 'uv.lock'
            uv_lock_backup_path = tmp_path / 'uv.lock.bak'
            uv_lock_backup_path.write_text('version = 1\n[package]\nfoo = "1.0.0"\n', encoding='utf-8')
            uv_lock_path.write_text('version = 1\n[package]\nfoo = "1.1.0"\nbar = "0.2.0"\n', encoding='utf-8')
            result = updater.compare_uv_lock_files(uv_lock_path, uv_lock_backup_path)
        self.assertIsInstance(result, dict)
        self.assertTrue(result['changes'])
        diff_text: str = result['diff']
        self.assertIn(str(uv_lock_backup_path), diff_text)
        self.assertIn(str(uv_lock_path), diff_text)
        self.assertIn('+bar = "0.2.0"', diff_text)
        self.assertIn('-foo = "1.0.0"', diff_text)
        self.assertIn('+foo = "1.1.0"', diff_text)

    def test_compare_uv_lock_files_failure_returns_empty_result(self) -> None:
        """
        Checks that compare_uv_lock_files() returns no changes and empty diff when comparison fails.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            uv_lock_path = tmp_path / 'uv.lock'
            uv_lock_path.write_text('content\n', encoding='utf-8')
            missing_backup = tmp_path / 'does_not_exist.lock.bak'
            result = updater.compare_uv_lock_files(uv_lock_path, missing_backup)
        self.assertFalse(result['changes'])
        self.assertEqual(result['diff'], '')

    def test_run_upgrade_sync_failure_sends_email_and_raises(self) -> None:
        """
        Checks that staging sync failure restores from backup, verifies rollback, emails admins, and raises.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            project_path = tmp_path / 'project'
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / 'uv.lock').write_text('version = 1\n', encoding='utf-8')
            (project_path.parent / 'uv.lock.bak').write_text('version = 1\n', encoding='utf-8')
            failure_result = subprocess.CompletedProcess(args=['uv', 'sync'], returncode=2, stdout='', stderr='sync failed')
            restore_result = subprocess.CompletedProcess(
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
            with patch('subprocess.run', side_effect=[failure_result, restore_result, run_tests_result]):
                with patch('lib.lib_emailer.Emailer.send_email', return_value=None) as mock_send:
                    with self.assertRaises(Exception):
                        updater.run_upgrade_sync(
                            Path('uv'),
                            project_path,
                            'staging',
                            [('Admin', 'admin@example.com')],
                        )
            mock_send.assert_called_once()

    def test_run_locked_sync_failure_sends_email_and_raises_without_tests(self) -> None:
        """
        Checks that production locked sync failure emails admins and does not run rollback tests.
        """
        updater = UvUpdater()
        failure_result = subprocess.CompletedProcess(args=['uv', 'sync'], returncode=2, stdout='', stderr='sync failed')
        with patch('subprocess.run', return_value=failure_result):
            with patch.object(updater, 'verify_staging_rollback') as mock_verify:
                with patch('lib.lib_emailer.Emailer.send_email', return_value=None) as mock_send:
                    with self.assertRaises(Exception):
                        updater.run_locked_sync(
                            Path('uv'),
                            Path('/tmp/project'),
                            'production',
                            [('Admin', 'admin@example.com')],
                        )
        mock_verify.assert_not_called()
        mock_send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
