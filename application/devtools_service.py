"""
# mypy: ignore-errors
application/devtools_service.py — use-case layer for the Dev-tool
Integrations bounded context
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

Orchestrates domain/devtools.py + infrastructure/local_storage/
devtools_store.py + infrastructure/github_api/github_gateway.py +
infrastructure/anthropic_api/devtools_gateway.py — no print() of its own.
Extracted 2026-08-20 from claude_git.py, claude_github.py, and
claude_chrome.py's non-CLI bodies.

browse_session()'s on_step callback follows the same convention as
agents_gateway.py's on_step/on_delta (see exec-planning.md's Phase C
history for that convention's origin) and observability_service.py's
eval_run() on_case — print() moved entirely to interfaces/, this layer
just narrates events.
"""

from collections.abc import Callable
from urllib.parse import urljoin

from domain.devtools import (
    GITHUB_PR_DESCRIPTION_SYSTEM_PROMPT,
    GITHUB_REVIEW_SYSTEM_PROMPT,
    GITHUB_SUMMARISE_SYSTEM_PROMPT,
    GITHUB_TRIAGE_SYSTEM_PROMPT,
    BrowseStep,
    blame_explain_prompt,
    browse_turn_prompt,
    changelog_prompt,
    commit_message_prompt,
    commits_context,
    diff_review_prompt,
    domain_allowed,
    parse_json_action,
    pr_description_gh_prompt,
    pr_description_prompt,
    review_pr_context,
    triage_context,
)
from infrastructure.anthropic_api.devtools_gateway import (
    browse_decide,
    fetch_page,
    git_generate,
    github_generate,
    make_coder,
)
from infrastructure.github_api.github_gateway import fetch_diff as gh_fetch_diff
from infrastructure.github_api.github_gateway import get as gh_get
from infrastructure.github_api.github_gateway import resolve_token
from infrastructure.local_storage.devtools_store import (
    commit_with_message,
    get_changelog_log,
    get_commit_log,
    get_diff_stat,
    get_file_blame_log,
    get_staged_diff,
    read_file_lines,
    write_text_file,
)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── git ───────────────────────────────────────────────────────────────


def staged_diff(cwd: str = ".") -> str:
    return get_staged_diff(cwd)


def commit_message(diff: str, api_key: str, model: str, style: str = "conventional") -> str:
    return git_generate(api_key, model, commit_message_prompt(diff, style), max_tokens=256)


def pr_description(base: str, head: str, cwd: str, api_key: str, model: str) -> str:
    log = get_commit_log(base, head, cwd)
    diff_stat = get_diff_stat(base, head, cwd)
    return git_generate(api_key, model, pr_description_prompt(base, head, log, diff_stat), max_tokens=1024)


def changelog(since_tag: str, cwd: str, api_key: str, model: str) -> str:
    log = get_changelog_log(since_tag, cwd)
    if not log:
        return "(no commits since that tag)"
    return git_generate(api_key, model, changelog_prompt(since_tag, log), max_tokens=1024)


def diff_review(diff: str, api_key: str, model: str) -> str:
    return git_generate(api_key, model, diff_review_prompt(diff), max_tokens=2048)


def explain_blame(file: str, line_start: int, line_end: int, cwd: str, api_key: str, model: str) -> str:
    blame = get_file_blame_log(file, cwd)
    code = read_file_lines(cwd, file, line_start, line_end)
    return git_generate(
        api_key, model, blame_explain_prompt(file, line_start, line_end, blame, code), max_tokens=512
    )


def commit_and_write(message: str, cwd: str = ".") -> tuple[bool, str]:
    return commit_with_message(message, cwd)


def save_text(path: str, text: str) -> None:
    write_text_file(path, text)


# ── github ────────────────────────────────────────────────────────────


def resolve_github_token(explicit: str | None) -> str:
    return resolve_token(explicit)


def review_pr(repo: str, pr_number: int, gh_token: str, api_key: str, model: str) -> str:
    pr = gh_get(f"/repos/{repo}/pulls/{pr_number}", gh_token)
    diff = gh_fetch_diff(pr.get("diff_url", ""), gh_token, 15000)
    context = review_pr_context(pr_number, pr, diff)
    return github_generate(api_key, model, GITHUB_REVIEW_SYSTEM_PROMPT, context)


def triage_issues(repo: str, max_items: int, gh_token: str, api_key: str, model: str) -> str:
    issues_raw = gh_get(f"/repos/{repo}/issues?state=open&per_page={max_items}", gh_token)
    ctx = triage_context(repo, issues_raw)
    if ctx is None:
        return f"Unexpected response: {str(issues_raw)[:200]}"
    return github_generate(api_key, model, GITHUB_TRIAGE_SYSTEM_PROMPT, ctx)


def summarise_commits(repo: str, max_items: int, gh_token: str, api_key: str, model: str) -> str:
    commits_raw = gh_get(f"/repos/{repo}/commits?per_page={max_items}", gh_token)
    ctx = commits_context(repo, commits_raw)
    if ctx is None:
        return f"Unexpected response: {str(commits_raw)[:200]}"
    return github_generate(api_key, model, GITHUB_SUMMARISE_SYSTEM_PROMPT, ctx)


def generate_pr_description_gh(repo: str, pr_number: int, gh_token: str, api_key: str, model: str) -> str:
    pr = gh_get(f"/repos/{repo}/pulls/{pr_number}", gh_token)
    diff = gh_fetch_diff(pr.get("diff_url", ""), gh_token, 12000)
    return github_generate(
        api_key, model, GITHUB_PR_DESCRIPTION_SYSTEM_PROMPT, pr_description_gh_prompt(pr, diff)
    )


# ── browse ────────────────────────────────────────────────────────────


def browse_session(
    api_key: str,
    model: str,
    start_url: str,
    task: str,
    max_steps: int = 6,
    allowed_domains: list[str] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    on_step: Callable[[BrowseStep], None] = _NOOP,
) -> str | None:
    coder = make_coder(api_key, model, temperature, max_tokens)
    on_step(BrowseStep(step=0, url=start_url, action="start", detail=coder.model))

    url = start_url
    visited = set()
    for step in range(1, max_steps + 1):
        if url in visited:
            on_step(BrowseStep(step, url, "loop_detected"))
            break
        if not domain_allowed(url, allowed_domains):
            on_step(BrowseStep(step, url, "blocked"))
            break
        visited.add(url)

        on_step(BrowseStep(step, url, "fetching", detail=f"{step}/{max_steps}"))
        text, links, error = fetch_page(url)
        if error:
            on_step(BrowseStep(step, url, "fetch_error", detail=error))
            break

        reply = browse_decide(coder, browse_turn_prompt(task, url, text))
        decision = parse_json_action(reply)
        if decision is None:
            on_step(BrowseStep(step, url, "unparsable", detail=reply))
            return reply

        if decision["action"] == "answer":
            answer = decision.get("text", "")
            on_step(BrowseStep(step, url, "answer", detail=answer))
            return answer

        if decision["action"] == "navigate":
            next_url = urljoin(url, decision.get("url", ""))
            on_step(BrowseStep(step, url, "navigate", detail=decision.get("reason", "")))
            url = next_url
            continue

    # Reached whenever the loop broke early (loop/blocked/fetch_error) OR
    # ran out of steps — matches claude_chrome.py's original unconditional
    # tail print+return after the for-loop; only the "unparsable" and
    # "answer" branches above return early instead. (v1.44.0: the old
    # trailing "unknown_action" branch was removed — parse_json_action()
    # already returns None for any action other than navigate/answer, so
    # it could never fire; unknown actions take the "unparsable" path.)
    on_step(BrowseStep(step=max_steps, url=url, action="max_steps"))
    return None
