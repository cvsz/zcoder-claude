"""
domain/devtools.py — Dev-tool Integrations domain layer
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

Pure data + pure functions for the bounded context covering
claude_git.py, claude_github.py, and claude_chrome.py. No I/O, no
print(), no `import anthropic`, no `import subprocess`, no
`urllib.request` here — those all belong to infrastructure/.

Three genuinely different sub-features share one domain module because
they share one application service (`application/devtools_service.py`)
per §3's bounded-context table — the prompt-building/parsing logic below
is grouped by sub-feature with a section header, not merged together.
"""

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import urlparse


# ── git (claude_git.py) ───────────────────────────────────────────────

GIT_SYSTEM_PROMPT = (
    "You are a senior software engineer writing git artifacts. "
    "Be concise, specific, and follow conventional commit conventions where applicable."
)

_COMMIT_STYLE_NOTES = {
    "conventional": "Use Conventional Commits format (type(scope): short desc).",
    "imperative":   "Use imperative mood (Add X, Fix Y, Remove Z).",
    "detailed":     "Include a subject line and a bullet-point body.",
}


def commit_message_prompt(diff: str, style: str = "conventional") -> str:
    style_note = _COMMIT_STYLE_NOTES.get(style, "")
    return f"{style_note}\nWrite a git commit message for this diff:\n\n{diff}"


def pr_description_prompt(base: str, head: str, log: str, diff_stat: str) -> str:
    return (
        f"Write a PR description (## Summary, ## Changes, ## Testing) for a pull "
        f"request from '{head}' into '{base}'.\n\nCommits:\n{log}\n\nFiles changed:\n{diff_stat}"
    )


def changelog_prompt(since_tag: str, log: str) -> str:
    return (
        f"Generate a Markdown changelog from these commits since {since_tag}. "
        "Group by: Features, Fixes, Docs, Chores.\n\n" + log
    )


def diff_review_prompt(diff: str) -> str:
    return (
        "Review this diff for bugs, style issues, and missing tests. "
        "Be specific — reference exact lines.\n\n" + diff
    )


def blame_explain_prompt(file: str, line_start: int, line_end: int, blame: str, code: str) -> str:
    return (
        f"Explain the history and purpose of {file} lines {line_start}–{line_end}.\n\n"
        f"Commit history for this file:\n{blame}\n\nCode:\n{code}"
    )


# ── github (claude_github.py) ────────────────────────────────────────

GITHUB_REVIEW_SYSTEM_PROMPT = (
    "You are a senior software engineer reviewing a pull request. "
    "Comment on correctness, style, test coverage, and potential issues. "
    "Be specific: cite file names and line context from the diff."
)

GITHUB_TRIAGE_SYSTEM_PROMPT = (
    "You are a project maintainer triaging a backlog. For each issue: "
    "suggest a severity (critical/high/medium/low), an appropriate label, "
    "whether it's a bug/feature/question, and one-sentence resolution advice. "
    "Format as a concise table."
)

GITHUB_SUMMARISE_SYSTEM_PROMPT = (
    "You are a technical writer summarising recent development activity. "
    "Group related commits thematically and highlight breaking changes, "
    "new features, bug fixes, and dependency updates."
)

GITHUB_PR_DESCRIPTION_SYSTEM_PROMPT = (
    "Write a clear, concise PR description in Markdown. Include: "
    "## Summary, ## Changes, ## Testing, ## Notes. "
    "No filler sentences. Return only the Markdown."
)


def review_pr_context(pr_number: int, pr: dict, diff: str) -> str:
    return (
        f"PR #{pr_number}: {pr.get('title', '')}\n"
        f"Author: {pr.get('user', {}).get('login', '')}\n"
        f"Branch: {pr.get('head', {}).get('ref', '')} → {pr.get('base', {}).get('ref', '')}\n"
        f"Body: {(pr.get('body') or '')[:1000]}\n\n"
        f"Diff (truncated to 15k chars):\n{diff}"
    )


def triage_context(repo: str, issues_raw) -> Optional[str]:
    """Returns None (caller should surface an "unexpected response" message)
    when the GitHub API didn't return the expected list shape."""
    if not isinstance(issues_raw, list):
        return None
    issues_text = "\n".join(
        f"#{i.get('number')} [{', '.join(l['name'] for l in i.get('labels', []))}] "
        f"{i.get('title', '')} — {(i.get('body') or '')[:200]}"
        for i in issues_raw
    )
    return f"Repository: {repo}\n\nOpen issues:\n{issues_text}"


def commits_context(repo: str, commits_raw) -> Optional[str]:
    if not isinstance(commits_raw, list):
        return None
    commits_text = "\n".join(
        f"- [{c['sha'][:7]}] {c['commit']['message'].splitlines()[0]} "
        f"({c['commit']['author']['name']}, {c['commit']['author']['date'][:10]})"
        for c in commits_raw
    )
    return f"Repository: {repo}\n\nRecent commits:\n{commits_text}"


def pr_description_gh_prompt(pr: dict, diff: str) -> str:
    return f"PR title: {pr.get('title', '')}\nDiff:\n{diff}"


# ── chrome / browse (claude_chrome.py) ───────────────────────────────

MAX_PAGE_CHARS = 8000  # keep pages small enough to stay a cheap loop step

BROWSE_SYSTEM_PROMPT = """\
You are a headless browsing agent embedded in a CLI tool. Each turn you \
are given the current page's URL, its extracted text (including links as \
[text](url)), and a task. Decide the single next action.

Respond with ONLY a JSON object, no other text, in one of these shapes:

  {"action": "navigate", "url": "https://...", "reason": "why"}
  {"action": "answer", "text": "final answer to the task"}

Use "navigate" to follow a link relevant to the task (resolve relative \
links against the current page yourself if given one). Use "answer" as \
soon as you can complete the task from what you've seen — don't navigate \
more than necessary. If you get stuck (broken links, irrelevant content, \
paywall), use "answer" and say so plainly rather than guessing.
"""


class TextExtractor(HTMLParser):
    """Minimal HTML→text: strips tags/script/style, keeps <a href> as
    [text](url). Pure parsing — no network I/O of its own; the caller
    feeds it already-fetched HTML."""

    def __init__(self):
        super().__init__()
        self.chunks = []
        self.links = []
        self._skip = 0
        self._current_href = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._current_href = href

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip > 0:
            self._skip -= 1
        if tag == "a":
            self._current_href = None

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._current_href:
            self.links.append((text, self._current_href))
            self.chunks.append(f"[{text}]({self._current_href})")
        else:
            self.chunks.append(text)

    def text(self) -> str:
        return " ".join(self.chunks)[:MAX_PAGE_CHARS]


def extract_page_text(html: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Runs TextExtractor over already-fetched HTML. Returns (text, links).
    Raises on parse failure — callers decide how to report that (the
    original wrapped this in a broad except; the gateway layer still does,
    since a malformed page is an I/O-adjacent failure mode, not a domain
    concern)."""
    extractor = TextExtractor()
    extractor.feed(html)
    return extractor.text(), extractor.links


def domain_allowed(url: str, allowed_domains: Optional[List[str]]) -> bool:
    if not allowed_domains:
        return True
    host = urlparse(url).netloc.lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed_domains)


def parse_json_action(reply: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if data.get("action") not in ("navigate", "answer"):
        return None
    return data


def browse_turn_prompt(task: str, url: str, page_text: str) -> str:
    return (
        f"Task: {task}\n\nCurrent URL: {url}\n\n"
        f"Page text (truncated to {MAX_PAGE_CHARS} chars):\n{page_text}"
    )


@dataclass
class BrowseStep:
    """One step of a browsing-agent session — the pure "what happened"
    record; the CLI layer decides how to print it."""
    step: int
    url: str
    action: str  # "fetching" | "loop_detected" | "blocked" | "fetch_error" |
                 # "answer" | "navigate" | "unparsable" | "unknown_action" | "max_steps"
    detail: str = ""
