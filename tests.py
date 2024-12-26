# /// script
# requires-python = "~=3.12.0"
# dependencies = ["python-dotenv"]
# ///


"""
Usage:

uv run ./tests.py
"""

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
        file_a_new_path = Path('./test_docs/no_differences_A/file_a.txt').resolve()
        file_b_old_path = Path('./test_docs/no_differences_A/file_b.txt').resolve()
        project_path = None
        expected = False
        change_check_result = self_updater.compare_with_previous_backup(file_a_new_path, file_b_old_path, project_path)
        self.assertEqual(expected, change_check_result)

    def test__compare_with_previous_backup__no_differences_B(self):
        """
        Files A and B differ in date in comment-line, A has "ACTIVE" in comment-line -- so should be considered equal.
        """
        file_a_new_path = Path('./test_docs/no_differences_B/file_a.txt').resolve()
        file_b_old_path = Path('./test_docs/no_differences_B/file_b.txt').resolve()
        project_path = None
        expected = False
        change_check_result = self_updater.compare_with_previous_backup(file_a_new_path, file_b_old_path, project_path)
        self.assertEqual(expected, change_check_result)

    def test__compare_with_previous_backup__differences(self):
        """
        Files A and B differ in actual package version, so should be considered different.
        """
        file_a_new_path = Path('./test_docs/differences/file_a.txt').resolve()
        file_b_old_path = Path('./test_docs/differences/file_b.txt').resolve()
        project_path = None
        expected = True
        change_check_result = self_updater.compare_with_previous_backup(file_a_new_path, file_b_old_path, project_path)
        self.assertEqual(expected, change_check_result)


if __name__ == '__main__':
    unittest.main()
