import unittest
from pathlib import Path
from unittest.mock import patch

from lib.lib_uv_updater import UvUpdater


class TestUvUpdater(unittest.TestCase):
    def test_make_sync_command_includes_exclude_newer(self) -> None:
        updater = UvUpdater()
        uv_path = Path('/usr/local/bin/uv')
        with patch.object(updater, 'make_iso_date', return_value='2025-01-01'):
            sync_command = updater.make_sync_command(uv_path, 'local', '--upgrade')
        expected_command = [
            str(uv_path),
            'sync',
            '--upgrade',
            '--group',
            'local',
            '--exclude-newer',
            '2025-01-01',
        ]
        self.assertEqual(expected_command, sync_command)


if __name__ == '__main__':
    unittest.main()
