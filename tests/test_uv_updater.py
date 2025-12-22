import datetime
import unittest
from pathlib import Path
import tempfile

from lib.lib_uv_updater import UvUpdater


class TestUvUpdater(unittest.TestCase):
    def test_make_sync_command_includes_exclude_newer(self) -> None:
        updater = UvUpdater()
        uv_path = Path('/made/up/path')
        sync_command = updater.make_sync_command(uv_path, 'local', 'foo')
        self.assertIn('--exclude-newer', sync_command)
        exclude_newer_index = sync_command.index('--exclude-newer')
        self.assertLess(exclude_newer_index + 1, len(sync_command))
        iso_date_str = sync_command[exclude_newer_index + 1]
        datetime.datetime.strptime(iso_date_str, '%Y-%m-%d')  # ensures valid ISO date
        self.assertEqual([str(uv_path), 'sync', 'foo', '--group', 'local'], sync_command[:5])

    def test_compare_uv_lock_files_happy_path_returns_diff(self) -> None:
        """
        Checks that compare_uv_lock_files() returns a dict indicating changes with unified diff text when files differ.
        """
        updater = UvUpdater()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            uv_lock_path = tmp_path / 'uv.lock'
            uv_lock_backup_path = tmp_path / 'uv.lock.bak'

            # previous (backup) content
            uv_lock_backup_path.write_text(
                "version = 1\n"
                "[package]\n"
                "foo = \"1.0.0\"\n"
            )

            # current content (changed)
            uv_lock_path.write_text(
                "version = 1\n"
                "[package]\n"
                "foo = \"1.1.0\"\n"
                "bar = \"0.2.0\"\n"
            )

            result = updater.compare_uv_lock_files(uv_lock_path, uv_lock_backup_path)

            self.assertIsInstance(result, dict)
            self.assertIn('changes', result)
            self.assertIn('diff', result)
            self.assertTrue(result['changes'])
            diff_text: str = result['diff']
            self.assertNotEqual(diff_text.strip(), "")
            # Expect unified diff headers to reference the two files
            self.assertIn(str(uv_lock_backup_path), diff_text)
            self.assertIn(str(uv_lock_path), diff_text)
            # Expect to see changed line indicators
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
            self.assertEqual(result.get('diff', None), "")


if __name__ == '__main__':
    unittest.main()
