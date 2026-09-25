#!/usr/bin/env python3
"""Prepend one merged pull request to the repository changelog."""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Iterable

PR_MARKER = re.compile(r"<!-- pr:(\d+) -->")
DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})$")
CURSOR_PREFIX = "<!-- changelog-through:"
CURSOR_MARKER = re.compile(r"<!-- changelog-through:([0-9a-fA-F]{40}) -->")
GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+.!|>~])")
DEFAULT_CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


class IncompleteCompareResults(ValueError):
    """Raised when compare API pages do not cover the advertised commit count."""


def validate_sha(sha: str, name: str) -> str:
    if not GIT_SHA.fullmatch(sha):
        raise ValueError(f"{name} must be a 40-character hexadecimal Git SHA")
    return sha.lower()


def read_changelog_cursor(content: str) -> str | None:
    marker_count = content.count(CURSOR_PREFIX)
    if marker_count == 0:
        return None
    if marker_count != 1:
        raise ValueError("CHANGELOG.md must contain at most one cursor marker")

    marker_lines = [line.strip() for line in content.splitlines() if CURSOR_PREFIX in line]
    if len(marker_lines) != 1:
        raise ValueError("changelog cursor marker must be on its own line")
    match = CURSOR_MARKER.fullmatch(marker_lines[0])
    if match is None:
        raise ValueError("changelog cursor marker must contain a 40-character hexadecimal SHA")
    return match.group(1).lower()


def resolve_compare_range(content: str, push_before: str, push_after: str) -> tuple[str, str]:
    fallback = validate_sha(push_before, "PUSH_BEFORE")
    after = validate_sha(push_after, "PUSH_AFTER")
    return read_changelog_cursor(content) or fallback, after


def advance_cursor_if_updated(path: Path, push_after: str, added_entries: int) -> bool:
    if added_entries < 0:
        raise ValueError("added_entries cannot be negative")
    if added_entries == 0:
        return False

    sha = validate_sha(push_after, "PUSH_AFTER")
    content = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n\n"
    if not content.splitlines() or content.splitlines()[0].strip() != "# Changelog":
        raise ValueError("CHANGELOG.md must start with '# Changelog'")
    cursor = read_changelog_cursor(content)
    lines = content.splitlines()
    marker_line = f"{CURSOR_PREFIX}{sha} -->"

    if cursor is not None:
        marker_index = next(index for index, line in enumerate(lines) if CURSOR_PREFIX in line)
        lines[marker_index] = marker_line
    else:
        insert_at = 1
        if insert_at < len(lines) and lines[insert_at] == "":
            insert_at += 1
        lines[insert_at:insert_at] = [marker_line, ""]

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return True


def changelog_entry(pr_number: int, title: str, merged_at: str) -> tuple[str, str]:
    if pr_number <= 0:
        raise ValueError("PR_NUMBER must be a positive integer")

    clean_title = " ".join("".join(character for character in title if character.isprintable()).split())
    if not clean_title:
        raise ValueError("PR_TITLE must contain printable characters")
    clean_title = html.escape(clean_title, quote=False)
    clean_title = MARKDOWN_SPECIAL.sub(r"\\\1", clean_title)

    timestamp = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    date = timestamp.astimezone(UTC).date().isoformat()
    return date, f"- PR #{pr_number}: {clean_title} <!-- pr:{pr_number} -->"


def update_changelog(path: Path, pr_number: int, title: str, merged_at: str) -> bool:
    entry_date, entry = changelog_entry(pr_number, title, merged_at)
    content = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n\n"

    if any(int(match.group(1)) == pr_number for match in PR_MARKER.finditer(content)):
        return False

    lines = content.splitlines()
    if not lines or lines[0].strip() != "# Changelog":
        raise ValueError("CHANGELOG.md must start with '# Changelog'")
    read_changelog_cursor(content)

    date_heading = f"## {entry_date}"
    target_date = date.fromisoformat(entry_date)
    date_headings: list[tuple[int, date]] = []
    for index, line in enumerate(lines):
        match = DATE_HEADING.fullmatch(line)
        if match:
            date_headings.append((index, date.fromisoformat(match.group(1))))

    existing_heading = next(
        ((index, heading_date) for index, heading_date in date_headings if heading_date == target_date),
        None,
    )
    if existing_heading is not None:
        heading_index, _ = existing_heading
        insert_at = heading_index + 1
        if insert_at < len(lines) and lines[insert_at] == "":
            insert_at += 1
        lines.insert(insert_at, entry)
    else:
        first_older_heading = next(
            (index for index, heading_date in date_headings if heading_date < target_date),
            None,
        )
        if first_older_heading is not None:
            lines[first_older_heading:first_older_heading] = [
                date_heading,
                "",
                entry,
                "",
            ]
        elif date_headings:
            lines.extend(["", date_heading, "", entry])
        else:
            insert_at = 1
            if insert_at < len(lines) and lines[insert_at] == "":
                insert_at += 1
            if insert_at < len(lines) and CURSOR_PREFIX in lines[insert_at]:
                insert_at += 1
                if insert_at < len(lines) and lines[insert_at] == "":
                    insert_at += 1
            lines[insert_at:insert_at] = [date_heading, "", entry, ""]

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return True


def collect_compare_commits(pages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect and validate all commit pages returned by GitHub's compare API."""
    expected_total: int | None = None
    commits: list[dict[str, Any]] = []
    seen_shas: set[str] = set()

    for page in pages:
        page_total = page.get("total_commits")
        page_commits = page.get("commits")
        if not isinstance(page_total, int) or isinstance(page_total, bool) or page_total < 0:
            raise ValueError("compare API page has an invalid total_commits")
        if not isinstance(page_commits, list):
            raise ValueError("compare API page has no commits array")
        if expected_total is None:
            expected_total = page_total
        elif page_total != expected_total:
            raise ValueError("compare API total_commits changed between pages")

        for commit in page_commits:
            if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str):
                raise ValueError("compare API returned a commit without a SHA")
            sha = commit["sha"]
            if sha in seen_shas:
                raise ValueError("compare API returned a duplicate commit across pages")
            seen_shas.add(sha)
            commits.append(commit)
            if len(commits) > expected_total:
                raise ValueError("compare API returned more commits than total_commits")

    if expected_total is None:
        raise ValueError("compare API returned no pages")
    if len(commits) < expected_total:
        raise IncompleteCompareResults(f"compare API returned {len(commits)} of {expected_total} commits")
    return commits


def github_api(url: str, token: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_compare_commits(repository: str, before: str, after: str, token: str) -> list[dict[str, Any]]:
    api_base = f"https://api.github.com/repos/{repository}"
    pages: list[dict[str, Any]] = []
    page_number = 1

    while True:
        query = urlencode({"per_page": 100, "page": page_number})
        page = github_api(f"{api_base}/compare/{before}...{after}?{query}", token)
        pages.append(page)
        try:
            return collect_compare_commits(pages)
        except IncompleteCompareResults:
            if not page.get("commits"):
                raise ValueError("compare API pagination stopped before all commits were returned")
            page_number += 1


def find_merged_prs(
    repository: str,
    before: str,
    after: str,
    default_branch: str,
    token: str,
    excluded_head_ref: str = "",
) -> list[dict[str, Any]]:
    api_base = f"https://api.github.com/repos/{repository}"
    if before and set(before) == {"0"}:
        commits = [{"sha": after}]
    elif before == after:
        commits = []
    else:
        commits = fetch_compare_commits(repository, before, after, token)

    merged_prs: dict[int, dict[str, Any]] = {}
    for commit in commits:
        commit_sha = commit.get("sha")
        if not commit_sha:
            continue
        associated = github_api(
            f"{api_base}/commits/{commit_sha}/pulls?{urlencode({'per_page': 100})}",
            token,
        )
        for pull_request in associated:
            merged_at = pull_request.get("merged_at")
            base = pull_request.get("base") or {}
            head = pull_request.get("head") or {}
            number = pull_request.get("number")
            if (
                merged_at
                and base.get("ref") == default_branch
                and head.get("ref") != excluded_head_ref
                and isinstance(number, int)
            ):
                merged_prs[number] = pull_request

    return sorted(
        merged_prs.values(),
        key=lambda pull_request: (pull_request["merged_at"], pull_request["number"]),
    )


def apply_pr_metadata(prs: list[dict[str, Any]], changelog_path: Path) -> int:
    updates = 0
    for pull_request in sorted(prs, key=lambda item: (str(item["merged_at"]), int(item["number"]))):
        if update_changelog(
            changelog_path,
            int(pull_request["number"]),
            str(pull_request["title"]),
            str(pull_request["merged_at"]),
        ):
            updates += 1
    return updates


def main() -> int:
    try:
        changelog_path = Path(os.environ.get("CHANGELOG_PATH", DEFAULT_CHANGELOG))
        if "PR_METADATA_JSON" in os.environ:
            prs = json.loads(os.environ["PR_METADATA_JSON"])
            if not isinstance(prs, list):
                raise ValueError("PR_METADATA_JSON must be a JSON array")
        elif "PR_NUMBER" in os.environ:
            prs = [
                {
                    "number": int(os.environ["PR_NUMBER"]),
                    "title": os.environ["PR_TITLE"],
                    "merged_at": os.environ["PR_MERGED_AT"],
                }
            ]
        else:
            content = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else "# Changelog\n\n"
            compare_before, compare_after = resolve_compare_range(
                content, os.environ["PUSH_BEFORE"], os.environ["PUSH_AFTER"]
            )
            prs = find_merged_prs(
                os.environ["GITHUB_REPOSITORY"],
                compare_before,
                compare_after,
                os.environ["DEFAULT_BRANCH"],
                os.environ["GITHUB_TOKEN"],
                os.environ.get("CHANGELOG_BOT_BRANCH", ""),
            )
        updates = apply_pr_metadata(prs, changelog_path)
        if "PR_NUMBER" not in os.environ and "PR_METADATA_JSON" not in os.environ:
            advance_cursor_if_updated(changelog_path, os.environ["PUSH_AFTER"], updates)
    except (HTTPError, URLError, KeyError, TypeError, ValueError) as error:
        print(f"changelog update failed: {error}", file=sys.stderr)
        return 1

    print(f"Added {updates} merged PR(s) to the changelog.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
