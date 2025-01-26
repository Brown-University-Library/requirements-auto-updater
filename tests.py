# /// script
# requires-python = "~=3.12.0"
# dependencies = ["python-dotenv~=1.0.0"]
# ///


"""
Usage:

uv run ./tests.py
"""

import logging
import sys
import unittest
from pathlib import Path

## set up logging ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
)
log = logging.getLogger(__name__)

# ## add project to path ----------------------------------------------
this_file_path = Path(__file__).resolve()
stuff_dir = this_file_path.parent.parent
sys.path.append(str(stuff_dir))
from self_updater_code import (  # noqa: E402 (disables linter warning that this import is not at the top)
    lib_django_updater,
    lib_git_handler,
)
from self_updater_code.lib_compilation_evaluator import CompiledComparator  # noqa: E402  (prevents linter problem-indicator)


class TestGitCommands(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_git_pull__A(self):
        """
        Checks that `Already up to date.` is detected properly.
        Assumes current-project is, actually, already up-to-date.
        """
        cur_dir = Path('./').resolve()
        log.debug(f'cur_dir: {cur_dir}')
        git_result: tuple[bool, dict] = lib_git_handler.run_git_pull(cur_dir)
        (ok, output) = git_result
        self.assertTrue(ok is True)
        self.assertIn('Already up to date.', output['stdout'])

    def test_git_status_clean(self):
        """
        Checks that `On branch main` is detected properly.
        Assumes current-project is on branch `main`.

        Note: just looking for the word 'clean' because one version of git says "working tree clean"
            and another says "working directory clean". TODO: consider just checking the ok boolean.
        """
        cur_dir = Path('./').resolve()
        log.debug(f'cur_dir: {cur_dir}')
        git_result: tuple[bool, dict] = lib_git_handler.run_git_status(cur_dir)
        (ok, output) = git_result
        self.assertTrue(ok is True)
        self.assertIn('clean', output['stdout'])

    def test_git_status_not_clean(self):
        """
        Checks that various non-"clean" states are detected properly.
        Assumes current-project is on branch `main`.
        """
        target_dir = Path('../git_tests/check_changes_not_staged/').resolve()
        log.debug(f'cur_dir: {target_dir}')
        git_result: tuple[bool, dict] = lib_git_handler.run_git_status(target_dir)
        (ok, output) = git_result
        self.assertTrue(ok is True)
        self.assertNotIn('clean', output['stdout'])


class TestMiscellaneous(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_check_for_django_update__no_django(self):
        """
        Check that django is not detected properly.
        """
        incoming_text = 'foo\nbar\nbaz\n'
        expected = False
        result = lib_django_updater.check_for_django_update(incoming_text)
        self.assertEqual(expected, result)

    def test_check_for_django_update__django_present(self):
        """
        Check that django is detected properly.
        """
        incoming_text = """
            --- staging_2025-01-14T02-00-05.txt
            +++ staging_2025-01-15T02-00-04.txt
            ---
            +++
            @@ -12,7 +12,7 @@
                #   httpx
            cffi==1.17.1 ; implementation_name != 'pypy' and os_name == 'nt'
                # via trio
            -django==4.2.17
            +django==4.2.18
                # via -r requirements/base.in
            h11==0.14.0
                # via httpcore
            """
        incoming_text: str = incoming_text.replace('            ', '')  # removes indentation-spaces
        expected = True
        result = lib_django_updater.check_for_django_update(incoming_text)
        self.assertEqual(expected, result)


class TestComparison(unittest.TestCase):
    def setUp(self):
        self.compiled_comparator = CompiledComparator()
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
        change_check_result = self.compiled_comparator.compare_with_previous_backup(
            file_a_new_path, file_b_old_path, project_path
        )
        self.assertEqual(expected, change_check_result)

    def test__compare_with_previous_backup__no_differences_B(self):
        """
        Files A and B differ in date in comment-line, A has "ACTIVE" in comment-line -- so should be considered equal.
        """
        file_a_new_path = Path('./test_docs/no_differences_B/file_a.txt').resolve()
        file_b_old_path = Path('./test_docs/no_differences_B/file_b.txt').resolve()
        project_path = None
        expected = False
        change_check_result = self.compiled_comparator.compare_with_previous_backup(
            file_a_new_path, file_b_old_path, project_path
        )
        self.assertEqual(expected, change_check_result)

    def test__compare_with_previous_backup__differences(self):
        """
        Files A and B differ in actual package version, so should be considered different.
        """
        file_a_new_path = Path('./test_docs/differences/file_a.txt').resolve()
        file_b_old_path = Path('./test_docs/differences/file_b.txt').resolve()
        project_path = None
        expected = True
        change_check_result = self.compiled_comparator.compare_with_previous_backup(
            file_a_new_path, file_b_old_path, project_path
        )
        self.assertEqual(expected, change_check_result)


if __name__ == '__main__':
    unittest.main()
