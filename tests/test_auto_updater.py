import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auto_updater


class TestManageUpdateDryRunGate(unittest.TestCase):
    def test_no_pending_change_skips_real_update_flow(self) -> None:
        """
        Checks that a no-op dry-run skips backup, sync, follow-up tests, git, and email.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir).resolve()
            common_patches = self._build_common_patches(project_path, 'Dry run found no pending changes.')
            with common_patches:
                auto_updater.manage_update(str(project_path))
                self.mock_inspect_pending_sync.assert_called_once()
                self.mock_backup_uv_lock.assert_not_called()
                self.mock_manage_sync.assert_not_called()
                self.mock_run_followup_tests.assert_not_called()
                self.mock_manage_git.assert_not_called()
                self.mock_send_email_of_diffs.assert_not_called()
                self.mock_update_group_and_permissions.assert_called_once_with(project_path, None, 'staff')

    def test_exclude_newer_only_change_skips_real_update_flow(self) -> None:
        """
        Checks that lockfile-only metadata churn skips backup, sync, follow-up tests, git, and email.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir).resolve()
            common_patches = self._build_common_patches(project_path, 'Dry run indicates lockfile-only metadata churn; skipping update.', True)
            with common_patches:
                auto_updater.manage_update(str(project_path))
                self.mock_inspect_pending_sync.assert_called_once()
                self.mock_backup_uv_lock.assert_not_called()
                self.mock_manage_sync.assert_not_called()
                self.mock_run_followup_tests.assert_not_called()
                self.mock_manage_git.assert_not_called()
                self.mock_send_email_of_diffs.assert_not_called()
                self.mock_update_group_and_permissions.assert_called_once_with(project_path, None, 'staff')

    def _build_common_patches(self, project_path: Path, summary: str, is_exclude_newer_only: bool = False):
        """
        Checks that common manage_update dependencies can be patched consistently for dry-run gate tests.
        """
        dry_run_result = {
            'has_pending_change': not summary.endswith('no pending changes.'),
            'is_substantive': False,
            'is_exclude_newer_only': is_exclude_newer_only,
            'summary': summary,
            'sync_action': 'check',
            'lock_action': 'check' if is_exclude_newer_only is False else 'write',
        }
        patchers = [
            patch('auto_updater.lib_environment_checker.validate_project_path', return_value=None),
            patch('auto_updater.os.chdir', return_value=None),
            patch('auto_updater.lib_environment_checker.determine_project_email_addresses', return_value=[('Admin', 'admin@example.com')]),
            patch('auto_updater.lib_environment_checker.check_branch', return_value=None),
            patch('auto_updater.lib_environment_checker.check_git_status', return_value=None),
            patch('auto_updater.lib_environment_checker.validate_pyproject_toml', return_value=None),
            patch('auto_updater.lib_environment_checker.determine_environment_type', return_value='staging'),
            patch('auto_updater.lib_environment_checker.validate_uv_path', return_value=None),
            patch('auto_updater.lib_environment_checker.determine_group', return_value='staff'),
            patch('auto_updater.lib_environment_checker.check_group_and_permissions', return_value=None),
            patch('auto_updater.run_initial_tests', return_value=None),
            patch('auto_updater.UvUpdater.inspect_pending_sync', return_value=dry_run_result),
            patch('auto_updater.UvUpdater.backup_uv_lock', return_value=project_path.parent / 'uv.lock.bak'),
            patch('auto_updater.UvUpdater.manage_sync', return_value=None),
            patch('auto_updater.run_followup_tests', return_value=None),
            patch('auto_updater.GitHandler.manage_git', return_value=(True, 'Success')),
            patch('auto_updater.send_email_of_diffs', return_value=None),
            patch('auto_updater.update_group_and_permissions', return_value=None),
        ]
        started_patches = [patcher.start() for patcher in patchers]
        (
            _validate_project_path,
            _os_chdir,
            _determine_project_email_addresses,
            _check_branch,
            _check_git_status,
            _validate_pyproject_toml,
            _determine_environment_type,
            _validate_uv_path,
            _determine_group,
            _check_group_and_permissions,
            _run_initial_tests,
            self.mock_inspect_pending_sync,
            self.mock_backup_uv_lock,
            self.mock_manage_sync,
            self.mock_run_followup_tests,
            self.mock_manage_git,
            self.mock_send_email_of_diffs,
            self.mock_update_group_and_permissions,
        ) = started_patches
        self.addCleanup(patch.stopall)
        return _NullContextManager()


class _NullContextManager:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


if __name__ == '__main__':
    unittest.main()
