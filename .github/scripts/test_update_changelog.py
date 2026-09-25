import tempfile
import unittest
from pathlib import Path

from update_changelog import (
    IncompleteCompareResults,
    advance_cursor_if_updated,
    changelog_entry,
    collect_compare_commits,
    resolve_compare_range,
    update_changelog,
)


class ChangelogHelpersTest(unittest.TestCase):
    def test_collects_all_compare_pages_and_rejects_incomplete_results(self) -> None:
        pages = [
            {"total_commits": 3, "commits": [{"sha": "a"}, {"sha": "b"}]},
            {"total_commits": 3, "commits": [{"sha": "c"}]},
        ]
        self.assertEqual(
            collect_compare_commits(pages),
            [{"sha": "a"}, {"sha": "b"}, {"sha": "c"}],
        )
        with self.assertRaises(IncompleteCompareResults):
            collect_compare_commits(pages[:1])

    def test_escapes_html_in_pr_title(self) -> None:
        _, entry = changelog_entry(
            7,
            "<script>& [title](https://example.invalid)",
            "2026-09-25T08:00:00Z",
        )
        self.assertNotIn("<script>", entry)
        self.assertIn("&lt;script&gt;&amp; \\[title\\]\\(https://example", entry)
        self.assertIn("\\.invalid\\)", entry)

    def test_delayed_entries_keep_date_sections_reverse_chronological(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            changelog = Path(directory) / "CHANGELOG.md"
            update_changelog(changelog, 1, "Newest", "2026-09-25T08:00:00Z")
            update_changelog(changelog, 2, "Oldest", "2026-09-23T08:00:00Z")
            update_changelog(changelog, 3, "Delayed", "2026-09-24T08:00:00Z")
            self.assertFalse(update_changelog(changelog, 3, "Duplicate", "2026-09-24T08:00:00Z"))

            content = changelog.read_text(encoding="utf-8")
            headings = [line for line in content.splitlines() if line.startswith("## ")]
            self.assertEqual(
                headings,
                ["## 2026-09-25", "## 2026-09-24", "## 2026-09-23"],
            )
            self.assertEqual(content.count("<!-- pr:3 -->"), 1)

    def test_existing_cursor_catches_up_from_last_successful_push(self) -> None:
        last_success = "1" * 40
        event_before = "2" * 40
        event_after = "3" * 40
        content = f"# Changelog\n\n<!-- changelog-through:{last_success} -->\n\n"

        self.assertEqual(
            resolve_compare_range(content, event_before, event_after),
            (last_success, event_after),
        )

    def test_new_entry_advances_cursor_to_push_after(self) -> None:
        push_after = "c" * 40
        with tempfile.TemporaryDirectory() as directory:
            changelog = Path(directory) / "CHANGELOG.md"
            update_changelog(changelog, 10, "Added entry", "2026-09-25T08:00:00Z")

            self.assertTrue(advance_cursor_if_updated(changelog, push_after, 1))
            content = changelog.read_text(encoding="utf-8")
            self.assertEqual(
                resolve_compare_range(content, "a" * 40, "b" * 40),
                (push_after, "b" * 40),
            )

    def test_no_added_entries_does_not_advance_cursor(self) -> None:
        cursor = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            changelog = Path(directory) / "CHANGELOG.md"
            original = f"# Changelog\n\n<!-- changelog-through:{cursor} -->\n\n"
            changelog.write_text(original, encoding="utf-8")

            self.assertFalse(advance_cursor_if_updated(changelog, "b" * 40, 0))
            self.assertEqual(changelog.read_text(encoding="utf-8"), original)

    def test_rejects_invalid_cursor_and_push_sha(self) -> None:
        with self.assertRaises(ValueError):
            resolve_compare_range(
                "# Changelog\n\n<!-- changelog-through:bad -->\n",
                "a" * 40,
                "b" * 40,
            )
        with self.assertRaises(ValueError):
            resolve_compare_range("# Changelog\n", "bad", "b" * 40)


if __name__ == "__main__":
    unittest.main()
