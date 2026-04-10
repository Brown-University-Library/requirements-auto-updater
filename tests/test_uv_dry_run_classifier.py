import textwrap
import unittest

from lib.lib_uv_dry_run_classifier import classify_dry_run_output


class TestUvDryRunClassifier(unittest.TestCase):
    def test_check_check_json_returns_no_pending_change(self) -> None:
        """
        Checks that check/check dry-run actions are treated as no pending changes.
        """
        output_text = textwrap.dedent(
            """\
            Resolved 2 packages in 16ms
            {
              "sync": {
                "action": "check"
              },
              "lock": {
                "action": "check"
              },
              "dry_run": true
            }
            Would make no changes
            """
        )
        result = classify_dry_run_output(output_text)
        self.assertFalse(result['has_pending_change'])
        self.assertFalse(result['is_substantive'])
        self.assertFalse(result['is_exclude_newer_only'])

    def test_lock_change_without_sync_change_returns_exclude_newer_only(self) -> None:
        """
        Checks that lock-only dry-run changes are treated as metadata-only.
        """
        output_text = textwrap.dedent(
            """\
            {
              "sync": {
                "action": "check"
              },
              "lock": {
                "action": "write"
              },
              "dry_run": true
            }
            """
        )
        result = classify_dry_run_output(output_text)
        self.assertTrue(result['has_pending_change'])
        self.assertFalse(result['is_substantive'])
        self.assertTrue(result['is_exclude_newer_only'])

    def test_sync_create_returns_substantive_change(self) -> None:
        """
        Checks that a non-check sync action is treated as a substantive change.
        """
        output_text = textwrap.dedent(
            """\
            {
              "sync": {
                "action": "create"
              },
              "lock": {
                "action": "check"
              },
              "dry_run": true
            }
            Would install 3 packages
            """
        )
        result = classify_dry_run_output(output_text)
        self.assertTrue(result['has_pending_change'])
        self.assertTrue(result['is_substantive'])
        self.assertFalse(result['is_exclude_newer_only'])

    def test_text_only_no_changes_returns_no_pending_change(self) -> None:
        """
        Checks that known no-change text is treated as no pending changes.
        """
        result = classify_dry_run_output('Resolved 2 packages in 4ms\nWould make no changes\n')
        self.assertFalse(result['has_pending_change'])
        self.assertFalse(result['is_substantive'])


if __name__ == '__main__':
    unittest.main()
