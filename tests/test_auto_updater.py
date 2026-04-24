import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auto_updater


class TestManageUpdateWorkflows(unittest.TestCase):
    def test_staging_no_pending_change_skips_real_update_flow(self) -> None:
        """
        Checks that a no-op staging dry-run skips sync, follow-up tests, git, and diff email.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir).resolve()
            dry_run_result = {
                'has_pending_change': False,
                'is_substantive': False,
                'is_exclude_newer_only': False,
                'summary': 'Dry run found no pending changes.',
                'sync_action': 'check',
                'lock_action': 'check',
            }
            with self._patch_common_dependencies(project_path, 'staging'):
                with patch('auto_updater.UvUpdater.inspect_pending_sync', return_value=dry_run_result) as mock_dry_run:
                    with patch('auto_updater.UvUpdater.backup_uv_lock') as mock_backup:
                        with patch('auto_updater.UvUpdater.run_upgrade_sync') as mock_upgrade_sync:
                            with patch('auto_updater.run_followup_tests') as mock_followup_tests:
                                with patch('auto_updater.GitHandler.manage_git') as mock_manage_git:
                                    with patch('auto_updater.handle_staging_failure_rollback') as mock_rollback:
                                        with patch('auto_updater.update_group_and_permissions') as mock_perms:
                                            auto_updater.manage_update(str(project_path))
            mock_dry_run.assert_called_once()
            mock_backup.assert_not_called()
            mock_upgrade_sync.assert_not_called()
            mock_followup_tests.assert_not_called()
            mock_manage_git.assert_not_called()
            mock_rollback.assert_not_called()
            mock_perms.assert_called_once_with(project_path, None, 'staff')

    def test_production_bypasses_staging_only_steps_and_runs_locked_sync(self) -> None:
        """
        Checks that production skips dry-run, lock backup, tests, and git while running locked sync.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir).resolve()
            with self._patch_common_dependencies(project_path, 'production'):
                with patch('auto_updater.UvUpdater.inspect_pending_sync') as mock_dry_run:
                    with patch('auto_updater.UvUpdater.backup_uv_lock') as mock_backup:
                        with patch('auto_updater.UvUpdater.run_locked_sync') as mock_locked_sync:
                            with patch(
                                'auto_updater.lib_django_updater.find_installed_package_version',
                                side_effect=['4.2.20', '4.2.27'],
                            ) as mock_find_version:
                                with patch('auto_updater.lib_django_updater.did_package_version_change', return_value=True):
                                    with patch('auto_updater.run_django_followup', return_value=None) as mock_django_followup:
                                        with patch('auto_updater.run_followup_tests') as mock_followup_tests:
                                            with patch('auto_updater.GitHandler.manage_git') as mock_manage_git:
                                                with patch(
                                                    'auto_updater.handle_staging_failure_rollback'
                                                ) as mock_rollback:
                                                    with patch(
                                                        'auto_updater.update_group_and_permissions'
                                                    ) as mock_perms:
                                                        auto_updater.manage_update(str(project_path))
            mock_dry_run.assert_not_called()
            mock_backup.assert_not_called()
            mock_locked_sync.assert_called_once_with(
                auto_updater.uv_path,
                project_path,
                'production',
                [('Admin', 'admin@example.com')],
            )
            self.assertEqual(mock_find_version.call_count, 2)
            mock_django_followup.assert_called_once_with(project_path, auto_updater.uv_path, True)
            mock_followup_tests.assert_not_called()
            mock_manage_git.assert_not_called()
            mock_rollback.assert_not_called()
            mock_perms.assert_called_once_with(project_path, None, 'staff')

    def _patch_common_dependencies(self, project_path: Path, environment_type: str):
        """
        Checks that shared preflight dependencies can be patched consistently.
        """
        patches = [
            patch('auto_updater.lib_environment_checker.validate_project_path', return_value=None),
            patch('auto_updater.os.chdir', return_value=None),
            patch('auto_updater.lib_environment_checker.determine_project_email_addresses', return_value=[('Admin', 'admin@example.com')]),
            patch('auto_updater.lib_environment_checker.check_branch', return_value=None),
            patch('auto_updater.lib_environment_checker.check_git_status', return_value=None),
            patch('auto_updater.lib_environment_checker.validate_pyproject_toml', return_value=None),
            patch('auto_updater.lib_environment_checker.determine_environment_type', return_value=environment_type),
            patch('auto_updater.lib_environment_checker.validate_uv_path', return_value=None),
            patch('auto_updater.lib_environment_checker.determine_group', return_value='staff'),
            patch('auto_updater.lib_environment_checker.check_default_directory_facls', return_value=None),
            patch('auto_updater.lib_environment_checker.check_group_and_permissions', return_value=None),
            patch('auto_updater.run_initial_tests', return_value=None),
        ]
        return _PatchContext(self, patches, project_path)


class _PatchContext:
    def __init__(self, test_case: unittest.TestCase, patches: list[patch], project_path: Path):
        self.test_case = test_case
        self.patches = patches
        self.project_path = project_path
        self.mocks: list[object] = []

    def __enter__(self) -> list[object]:
        self.mocks = [patcher.start() for patcher in self.patches]
        self.test_case.addCleanup(patch.stopall)
        return self.mocks

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


if __name__ == '__main__':
    unittest.main()
