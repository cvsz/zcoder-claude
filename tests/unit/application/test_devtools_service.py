"""tests/unit/application/test_devtools_service.py

Covers application/devtools_service.py — the use-case layer for the
Dev-tool Integrations bounded context, extracted 2026-08-20 (Phase D,
Context #8). Per this project's DoD (exec-planning.md §6), every function
here needs direct unit test coverage, not only indirect coverage via a
CLI test capturing stdout.
"""

import application.devtools_service as service
from domain.devtools import BrowseStep

# ── git ───────────────────────────────────────────────────────────────


def test_staged_diff_delegates_to_store(monkeypatch):
    monkeypatch.setattr(service, "get_staged_diff", lambda cwd: "the diff")
    assert service.staged_diff("/repo") == "the diff"


def test_commit_message_builds_prompt_and_calls_gateway(monkeypatch):
    seen = {}

    def fake_git_generate(api_key, model, prompt, max_tokens=1024):
        seen.update(api_key=api_key, model=model, prompt=prompt, max_tokens=max_tokens)
        return "feat: add thing"

    monkeypatch.setattr(service, "git_generate", fake_git_generate)

    result = service.commit_message("diff text", "key", "claude-sonnet-5")
    assert result == "feat: add thing"
    assert "diff text" in seen["prompt"]
    assert seen["max_tokens"] == 256


def test_pr_description_combines_log_and_diff_stat(monkeypatch):
    monkeypatch.setattr(service, "get_commit_log", lambda base, head, cwd: "log lines")
    monkeypatch.setattr(service, "get_diff_stat", lambda base, head, cwd: "stat lines")
    seen = {}

    def fake_git_generate(api_key, model, prompt, max_tokens=1024):
        seen["prompt"] = prompt
        return "PR text"

    monkeypatch.setattr(service, "git_generate", fake_git_generate)
    result = service.pr_description("main", "feat", "/repo", "key", "claude-sonnet-5")
    assert result == "PR text"
    assert "log lines" in seen["prompt"] and "stat lines" in seen["prompt"]


def test_changelog_returns_placeholder_when_no_commits(monkeypatch):
    monkeypatch.setattr(service, "get_changelog_log", lambda since_tag, cwd: "")
    result = service.changelog("v1.0", "/repo", "key", "claude-sonnet-5")
    assert result == "(no commits since that tag)"


def test_changelog_delegates_to_gateway_when_commits_exist(monkeypatch):
    monkeypatch.setattr(service, "get_changelog_log", lambda since_tag, cwd: "log")
    monkeypatch.setattr(service, "git_generate", lambda *a, **k: "changelog text")
    assert service.changelog("v1.0", "/repo", "key", "m") == "changelog text"


def test_diff_review_delegates_to_gateway(monkeypatch):
    monkeypatch.setattr(service, "git_generate", lambda *a, **k: "review text")
    assert service.diff_review("diff", "key", "m") == "review text"


def test_explain_blame_combines_blame_and_code(monkeypatch):
    monkeypatch.setattr(service, "get_file_blame_log", lambda file, cwd: "blame log")
    monkeypatch.setattr(service, "read_file_lines", lambda cwd, file, s, e: "code body")
    seen = {}

    def fake_git_generate(api_key, model, prompt, max_tokens=1024):
        seen["prompt"] = prompt
        return "explanation"

    monkeypatch.setattr(service, "git_generate", fake_git_generate)
    result = service.explain_blame("f.py", 1, 10, "/repo", "key", "m")
    assert result == "explanation"
    assert "blame log" in seen["prompt"] and "code body" in seen["prompt"]


def test_commit_and_write_delegates_to_store(monkeypatch):
    monkeypatch.setattr(service, "commit_with_message", lambda message, cwd: (True, ""))
    assert service.commit_and_write("msg", "/repo") == (True, "")


def test_save_text_delegates_to_store(monkeypatch):
    seen = {}
    monkeypatch.setattr(service, "write_text_file", lambda path, text: seen.update(path=path, text=text))
    service.save_text("out.md", "content")
    assert seen == {"path": "out.md", "text": "content"}


# ── github ────────────────────────────────────────────────────────────


def test_resolve_github_token_delegates(monkeypatch):
    monkeypatch.setattr(service, "resolve_token", lambda explicit: "resolved-token")
    assert service.resolve_github_token(None) == "resolved-token"


def test_review_pr_fetches_pr_and_diff_then_generates(monkeypatch):
    monkeypatch.setattr(service, "gh_get", lambda path, token: {"title": "t", "diff_url": "u"})
    monkeypatch.setattr(service, "gh_fetch_diff", lambda url, token, max_chars: "the diff")
    seen = {}

    def fake_github_generate(api_key, model, system, user, **k):
        seen["user"] = user
        return "review"

    monkeypatch.setattr(service, "github_generate", fake_github_generate)
    result = service.review_pr("o/r", 5, "tok", "key", "m")
    assert result == "review"
    assert "the diff" in seen["user"]


def test_triage_issues_returns_unexpected_message_on_bad_shape(monkeypatch):
    monkeypatch.setattr(service, "gh_get", lambda path, token: {"message": "Not Found"})
    result = service.triage_issues("o/r", 10, "tok", "key", "m")
    assert result.startswith("Unexpected response:")


def test_triage_issues_delegates_to_gateway_on_valid_shape(monkeypatch):
    monkeypatch.setattr(
        service, "gh_get", lambda path, token: [{"number": 1, "labels": [], "title": "t", "body": "b"}]
    )
    monkeypatch.setattr(service, "github_generate", lambda *a, **k: "triage result")
    assert service.triage_issues("o/r", 10, "tok", "key", "m") == "triage result"


def test_summarise_commits_returns_unexpected_message_on_bad_shape(monkeypatch):
    monkeypatch.setattr(service, "gh_get", lambda path, token: "oops")
    result = service.summarise_commits("o/r", 10, "tok", "key", "m")
    assert result.startswith("Unexpected response:")


def test_summarise_commits_delegates_to_gateway_on_valid_shape(monkeypatch):
    monkeypatch.setattr(
        service,
        "gh_get",
        lambda path, token: [
            {
                "sha": "abc1234",
                "commit": {"message": "m", "author": {"name": "a", "date": "2026-01-01T00:00:00Z"}},
            }
        ],
    )
    monkeypatch.setattr(service, "github_generate", lambda *a, **k: "summary result")
    assert service.summarise_commits("o/r", 10, "tok", "key", "m") == "summary result"


def test_generate_pr_description_gh_fetches_and_generates(monkeypatch):
    monkeypatch.setattr(service, "gh_get", lambda path, token: {"title": "t", "diff_url": "u"})
    monkeypatch.setattr(service, "gh_fetch_diff", lambda url, token, max_chars: "diff")
    monkeypatch.setattr(service, "github_generate", lambda *a, **k: "pr desc")
    assert service.generate_pr_description_gh("o/r", 3, "tok", "key", "m") == "pr desc"


# ── browse ────────────────────────────────────────────────────────────


class FakeCoder:
    model = "claude-sonnet-5"


def test_browse_session_answer_returns_immediately(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: ("page text", [], None))
    monkeypatch.setattr(
        service, "browse_decide", lambda coder, prompt: '{"action": "answer", "text": "the answer"}'
    )

    steps = []
    result = service.browse_session("key", "m", "https://x.com", "find X", on_step=steps.append)
    assert result == "the answer"
    actions = [s.action for s in steps]
    assert actions == ["start", "fetching", "answer"]


def test_browse_session_navigate_then_answer(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: ("page text", [], None))

    replies = iter(
        [
            '{"action": "navigate", "url": "/next", "reason": "looks relevant"}',
            '{"action": "answer", "text": "done"}',
        ]
    )
    monkeypatch.setattr(service, "browse_decide", lambda coder, prompt: next(replies))

    steps = []
    result = service.browse_session("key", "m", "https://x.com", "find X", on_step=steps.append)
    assert result == "done"
    actions = [s.action for s in steps]
    assert actions == ["start", "fetching", "navigate", "fetching", "answer"]
    # navigate target was resolved relative to the current page
    assert steps[3].url == "https://x.com/next"


def test_browse_session_loop_detected_hits_max_steps_tail(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: ("page text", [], None))
    # Always navigate right back to the start URL -> visited-set loop.
    monkeypatch.setattr(
        service,
        "browse_decide",
        lambda coder, prompt: '{"action": "navigate", "url": "https://x.com", "reason": "r"}',
    )

    steps = []
    result = service.browse_session("key", "m", "https://x.com", "find X", max_steps=3, on_step=steps.append)
    assert result is None
    actions = [s.action for s in steps]
    assert actions == ["start", "fetching", "navigate", "loop_detected", "max_steps"]


def test_browse_session_blocked_domain_hits_max_steps_tail(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    steps = []
    result = service.browse_session(
        "key", "m", "https://evil.com", "find X", allowed_domains=["good.com"], on_step=steps.append
    )
    assert result is None
    assert [s.action for s in steps] == ["start", "blocked", "max_steps"]


def test_browse_session_fetch_error_hits_max_steps_tail(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: (None, [], "boom"))
    steps = []
    result = service.browse_session("key", "m", "https://x.com", "find X", on_step=steps.append)
    assert result is None
    assert [s.action for s in steps] == ["start", "fetching", "fetch_error", "max_steps"]


def test_browse_session_unparsable_reply_returns_raw_reply(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: ("page text", [], None))
    monkeypatch.setattr(service, "browse_decide", lambda coder, prompt: "not json")
    steps = []
    result = service.browse_session("key", "m", "https://x.com", "find X", on_step=steps.append)
    assert result == "not json"
    assert [s.action for s in steps] == ["start", "fetching", "unparsable"]


def test_browse_session_action_outside_navigate_answer_is_unparsable(monkeypatch):
    """Confirms a genuine, pre-existing dead-code finding carried over
    faithfully from claude_chrome.py: domain.parse_json_action() already
    returns None for any action other than "navigate"/"answer" (see its
    own `if data.get("action") not in ("navigate", "answer"): return None`
    — a byte-exact port of the original _parse_json_action()), so
    browse_session()'s "unknown_action" on_step branch below can never
    actually fire; a syntactically-invalid-but-well-formed-JSON action
    like {"action": "delete"} takes the "unparsable" path instead, both
    in the original and here. Not "fixed" as part of this migration —
    changing runtime behavior wasn't in scope, only moving code."""
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: ("page text", [], None))
    monkeypatch.setattr(service, "browse_decide", lambda coder, prompt: '{"action": "delete"}')
    steps = []
    result = service.browse_session("key", "m", "https://x.com", "find X", on_step=steps.append)
    assert result == '{"action": "delete"}'  # returned verbatim as the "unparsable" reply
    assert [s.action for s in steps] == ["start", "fetching", "unparsable"]


def test_browse_session_default_on_step_is_a_noop(monkeypatch):
    monkeypatch.setattr(service, "make_coder", lambda *a, **k: FakeCoder())
    monkeypatch.setattr(service, "fetch_page", lambda url: ("page text", [], None))
    monkeypatch.setattr(service, "browse_decide", lambda coder, prompt: '{"action": "answer", "text": "ok"}')
    result = service.browse_session("key", "m", "https://x.com", "find X")  # should not raise
    assert result == "ok"


def test_browse_step_is_reused_as_the_on_step_payload_type():
    # sanity: BrowseStep is what's threaded through on_step, not some ad-hoc dict
    assert BrowseStep(step=1, url="u", action="fetching").action == "fetching"
