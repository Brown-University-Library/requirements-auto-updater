# /// script
# requires-python = "~=3.12.0"
# dependencies = ["python-dotenv"]
# ///

import unittest
from pathlib import Path

import self_updater


class TestSelfUpdater(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test__compare_with_previous_backup__no_differences_A(self):
        """
        Files A and B differ only in date in comment-line, so should be considered equal.
        """
        file_a_new_path = Path('./test_docs/file_a.txt')
        file_b_old_path = Path('./test_docs/file_b.txt')
        expected = False
        change_check_result = self_updater.compare_with_previous_backup(file_a_new_path, file_b_old_path)
        self.assertEqual(expected, change_check_result)


if __name__ == '__main__':
    unittest.main()
