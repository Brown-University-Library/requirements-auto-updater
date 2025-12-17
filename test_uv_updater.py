import datetime
import unittest
from pathlib import Path

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


if __name__ == '__main__':
    unittest.main()
