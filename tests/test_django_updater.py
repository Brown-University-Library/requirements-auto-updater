import unittest

from lib.lib_django_updater import check_for_django_update


class TestDjangoUpdater(unittest.TestCase):
    def test_check_for_django_update_happy_path_returns_true(self) -> None:
        """
        Checks that check_for_django_update() returns True when the diff shows a django addition ("+django==").
        """
        django_addition_diff_text = """
        --- a/uv.lock
        +++ b/uv.lock
        @@ -1,4 +1,4 @@
         version = 1
         [project]
        -django==5.1.2
        +django==5.1.3
        -somepkg==1.0.0
        +somepkg==1.1.0
        """.strip()
        self.assertTrue(check_for_django_update(django_addition_diff_text))

    def test_check_for_django_update_happy_path_returns_true_on_new_addition_only(self) -> None:
        """
        Checks that check_for_django_update() returns True when Django is newly added (no matching removal line).
        """
        django_new_addition_only_diff_text = """
        --- a/uv.lock
        +++ b/uv.lock
        @@ -1,3 +1,4 @@
         version = 1
         [project]
        -somepkg==1.0.0
        +somepkg==1.1.0
        +django==5.1.3
        """.strip()
        self.assertTrue(check_for_django_update(django_new_addition_only_diff_text))

    def test_check_for_django_update_failure_returns_false_when_no_exact_match(self) -> None:
        """
        Checks that check_for_django_update() returns False when there is no
        exact lowercase "+django==" addition (e.g., case-mismatch or only removals).
        """
        no_django_addition_diff_text = """
        --- a/uv.lock
        +++ b/uv.lock
        @@ -1,3 +1,3 @@
         version = 1
        -django==5.1.2
         [project]
        """.strip()
        self.assertFalse(check_for_django_update(no_django_addition_diff_text))

        case_mismatch_text = """
        --- a/uv.lock
        +++ b/uv.lock
        @@ -1,3 +1,4 @@
         version = 1
         [project]
        +Django==5.1.3
        """.strip()
        self.assertFalse(check_for_django_update(case_mismatch_text))


if __name__ == '__main__':
    unittest.main()
