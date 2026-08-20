"""tests/unit/domain/test_devtools.py

Covers domain/devtools.py — the pure data + logic layer for the Dev-tool
Integrations bounded context, extracted 2026-08-20 (Phase D, Context #8).
claude_git.py, claude_github.py, and claude_chrome.py had zero test
coverage before this migration; this closes that gap for the pure-logic
half of all three.
"""
from domain.devtools import (
    GIT_SYSTEM_PROMPT, commit_message_prompt, pr_description_prompt,
    changelog_prompt, diff_review_prompt, blame_explain_prompt,
    GITHUB_REVIEW_SYSTEM_PROMPT, GITHUB_TRIAGE_SYSTEM_PROMPT,
    GITHUB_SUMMARISE_SYSTEM_PROMPT, GITHUB_PR_DESCRIPTION_SYSTEM_PROMPT,
    review_pr_context, triage_context, commits_context, pr_description_gh_prompt,
    MAX_PAGE_CHARS, BROWSE_SYSTEM_PROMPT, extract_page_text,
    domain_allowed, parse_json_action, browse_turn_prompt, BrowseStep,
)


# ── git ───────────────────────────────────────────────────────────────

def test_git_system_prompt_mentions_conventions():
    assert "senior software engineer" in GIT_SYSTEM_PROMPT


def test_commit_message_prompt_conventional_style():
    p = commit_message_prompt("diff text", style="conventional")
    assert "Conventional Commits" in p
    assert "diff text" in p


def test_commit_message_prompt_unknown_style_has_no_style_note():
    p = commit_message_prompt("diff text", style="nonsense")
    assert p.startswith("\nWrite a git commit message")


def test_pr_description_prompt_includes_branches():
    p = pr_description_prompt("main", "feature", "log lines", "diff stat")
    assert "'feature'" in p and "'main'" in p
    assert "log lines" in p and "diff stat" in p


def test_changelog_prompt_includes_tag_and_log():
    p = changelog_prompt("v1.0", "commit log")
    assert "v1.0" in p and "commit log" in p


def test_diff_review_prompt_includes_diff():
    assert "some diff" in diff_review_prompt("some diff")


def test_blame_explain_prompt_includes_all_fields():
    p = blame_explain_prompt("f.py", 1, 10, "blame log", "code body")
    assert "f.py" in p and "1" in p and "10" in p
    assert "blame log" in p and "code body" in p


# ── github ────────────────────────────────────────────────────────────

def test_github_system_prompts_are_distinct():
    prompts = {GITHUB_REVIEW_SYSTEM_PROMPT, GITHUB_TRIAGE_SYSTEM_PROMPT,
              GITHUB_SUMMARISE_SYSTEM_PROMPT, GITHUB_PR_DESCRIPTION_SYSTEM_PROMPT}
    assert len(prompts) == 4


def test_review_pr_context_shapes_pr_metadata():
    pr = {"title": "Fix bug", "user": {"login": "alice"},
          "head": {"ref": "fix"}, "base": {"ref": "main"}, "body": "desc"}
    ctx = review_pr_context(42, pr, "the diff")
    assert "PR #42: Fix bug" in ctx
    assert "alice" in ctx and "fix" in ctx and "main" in ctx
    assert "the diff" in ctx


def test_triage_context_none_on_unexpected_shape():
    assert triage_context("r/r", {"message": "Not Found"}) is None


def test_triage_context_formats_issues_list():
    issues = [{"number": 1, "labels": [{"name": "bug"}], "title": "Crash", "body": "boom"}]
    ctx = triage_context("r/r", issues)
    assert "#1 [bug] Crash" in ctx


def test_commits_context_none_on_unexpected_shape():
    assert commits_context("r/r", "oops") is None


def test_commits_context_formats_commit_list():
    commits = [{"sha": "abcdef1234", "commit": {
        "message": "Fix thing\n\nmore detail", "author": {"name": "Bob", "date": "2026-08-19T00:00:00Z"}}}]
    ctx = commits_context("r/r", commits)
    assert "[abcdef1] Fix thing (Bob, 2026-08-19)" in ctx


def test_pr_description_gh_prompt_includes_title_and_diff():
    p = pr_description_gh_prompt({"title": "Add feature"}, "the diff")
    assert "Add feature" in p and "the diff" in p


# ── chrome / browse ───────────────────────────────────────────────────

def test_max_page_chars_reasonable():
    assert MAX_PAGE_CHARS == 8000


def test_browse_system_prompt_mentions_json_actions():
    assert "navigate" in BROWSE_SYSTEM_PROMPT and "answer" in BROWSE_SYSTEM_PROMPT


def test_text_extractor_strips_script_and_keeps_links():
    html = "<html><body><script>evil()</script><p>Hello <a href='/x'>link</a></p></body></html>"
    text, links = extract_page_text(html)
    assert "evil()" not in text
    assert "Hello" in text
    assert "[link](/x)" in text
    assert links == [("link", "/x")]


def test_text_extractor_truncates_to_max_page_chars():
    html = "<p>" + ("a" * 10000) + "</p>"
    text, _ = extract_page_text(html)
    assert len(text) <= MAX_PAGE_CHARS


def test_domain_allowed_no_restriction():
    assert domain_allowed("https://anything.com/page", None) is True


def test_domain_allowed_exact_match():
    assert domain_allowed("https://example.com/page", ["example.com"]) is True


def test_domain_allowed_subdomain_match():
    assert domain_allowed("https://docs.example.com/page", ["example.com"]) is True


def test_domain_allowed_rejects_other_domain():
    assert domain_allowed("https://evil.com/page", ["example.com"]) is False


def test_parse_json_action_navigate():
    reply = 'Sure, {"action": "navigate", "url": "https://x.com", "reason": "why"} done'
    d = parse_json_action(reply)
    assert d["action"] == "navigate"
    assert d["url"] == "https://x.com"


def test_parse_json_action_answer():
    d = parse_json_action('{"action": "answer", "text": "the answer"}')
    assert d["action"] == "answer"


def test_parse_json_action_no_json_returns_none():
    assert parse_json_action("no json here") is None


def test_parse_json_action_malformed_json_returns_none():
    assert parse_json_action("{not valid json}") is None


def test_parse_json_action_invalid_action_returns_none():
    assert parse_json_action('{"action": "delete"}') is None


def test_browse_turn_prompt_includes_task_url_and_text():
    p = browse_turn_prompt("find X", "https://x.com", "page body")
    assert "find X" in p and "https://x.com" in p and "page body" in p


def test_browse_step_defaults_detail_to_empty_string():
    s = BrowseStep(step=1, url="https://x.com", action="fetching")
    assert s.detail == ""
