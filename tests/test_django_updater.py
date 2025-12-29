import unittest
import textwrap

from lib.lib_django_updater import check_for_django_update


class TestDjangoUpdater(unittest.TestCase):
    def test_version_bump_in_uv_lock_diff_returns_true(self) -> None:
        """
        Checks that a version bump within Django's [[package]] block returns True.
        """
        diff_text = textwrap.dedent("""\
        --- a/uv.lock
        +++ b/uv.lock
         [[package]]
          name = "django"
         -version = "4.2.20"
         +version = "4.2.27"
          requires-python = ">=3.9"
        
""")
        self.assertTrue(check_for_django_update(diff_text))

    def test_wheels_only_changes_return_false(self) -> None:
        """
        Checks that changes to files/hashes only (no version change) return False.
        """
        diff_text = textwrap.dedent("""\
        --- a/uv.lock
        +++ b/uv.lock
         [[package]]
          name = "django"
          version = "4.2.27"
         -files = [
         -  {file = "django-4.2.27-py3-none-any.whl", hash = "sha256:OLD"},
         -]
         +files = [
         +  {file = "django-4.2.27-py3-none-any.whl", hash = "sha256:NEW"},
         +]
        
""")
        self.assertFalse(check_for_django_update(diff_text))

    def test_same_version_lines_return_false(self) -> None:
        """
        Checks that if both -version and +version are the same, returns False.
        """
        diff_text = textwrap.dedent("""\
        --- a/uv.lock
        +++ b/uv.lock
         [[package]]
          name = "django"
         -version = "4.2.27"
         +version = "4.2.27"
        
""")
        self.assertFalse(check_for_django_update(diff_text))

    def test_case_insensitive_name_matching_returns_true(self) -> None:
        """
        Checks that name = "Django" (capitalized) still matches and detects a bump.
        """
        diff_text = textwrap.dedent("""\
        --- a/uv.lock
        +++ b/uv.lock
         [[package]]
          name = "Django"
         -version = "4.2.20"
         +version = "4.2.27"
        
""")
        self.assertTrue(check_for_django_update(diff_text))


if __name__ == '__main__':
    unittest.main()
