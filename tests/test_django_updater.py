import unittest
import textwrap
import tempfile
from pathlib import Path

from lib.lib_django_updater import (
    check_for_django_update,
    did_package_version_change,
    find_installed_package_version,
)


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
         requires-python = ">="3.9
        
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

    def test_find_installed_package_version_returns_dist_info_version(self) -> None:
        """
        Checks that installed package version lookup reads the Django dist-info metadata.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            metadata_path = project_path / '.venv/lib/python3.12/site-packages/Django-4.2.27.dist-info/METADATA'
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text('Name: Django\nVersion: 4.2.27\n', encoding='utf-8')
            version = find_installed_package_version(project_path, 'django')
        self.assertEqual(version, '4.2.27')

    def test_did_package_version_change_requires_new_installed_version(self) -> None:
        """
        Checks that package change detection requires a different non-empty post-sync version.
        """
        self.assertTrue(did_package_version_change('4.2.20', '4.2.27'))
        self.assertFalse(did_package_version_change('4.2.27', '4.2.27'))
        self.assertFalse(did_package_version_change('4.2.27', None))


if __name__ == '__main__':
    unittest.main()
