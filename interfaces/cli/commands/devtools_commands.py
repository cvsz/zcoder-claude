"""
interfaces/cli/commands/devtools_commands.py — CLI presentation for the
Dev-tool Integrations bounded context
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

Only print() lives here — all real work delegated to
application/devtools_service.py. Extracted 2026-08-20 from
claude_git.py's cmd_git_commit/cmd_git_pr/cmd_git_changelog/
cmd_git_review/cmd_git_blame_explain, claude_github.py's
cmd_gh_review_pr/cmd_gh_triage/cmd_gh_commits/cmd_gh_pr_description, and
claude_chrome.py's cmd_browse (its print()-per-loop-step body converted
to an on_step callback that reproduces every original message exactly).
"""

from application import devtools_service as service
from domain.devtools import BrowseStep

__all__ = [
    "cmd_git_commit",
    "cmd_git_pr",
    "cmd_git_changelog",
    "cmd_git_review",
    "cmd_git_blame_explain",
    "cmd_gh_review_pr",
    "cmd_gh_triage",
    "cmd_gh_commits",
    "cmd_gh_pr_description",
    "cmd_browse",
]


# ── git ───────────────────────────────────────────────────────────────


def cmd_git_commit(
    api_key: str, model: str, style: str = "conventional", cwd: str = ".", write: bool = False
):
    diff = service.staged_diff(cwd)
    msg = service.commit_message(diff, api_key, model, style)
    print(msg)
    if write:
        success, err = service.commit_and_write(msg, cwd)
        if success:
            print("\n✓ Committed.")
        else:
            print(f"\n✗ Commit failed:\n{err}")


def cmd_git_pr(base: str, head: str, api_key: str, model: str, cwd: str = "."):
    print(service.pr_description(base, head, cwd, api_key, model))


def cmd_git_changelog(since_tag: str, api_key: str, model: str, cwd: str = ".", output: str | None = None):
    md = service.changelog(since_tag, cwd, api_key, model)
    if output:
        service.save_text(output, md)
        print(f"✓ Changelog saved to {output}")
    else:
        print(md)


def cmd_git_review(api_key: str, model: str, cwd: str = "."):
    diff = service.staged_diff(cwd)
    print(service.diff_review(diff, api_key, model))


def cmd_git_blame_explain(
    file: str, line_start: int, line_end: int, api_key: str, model: str, cwd: str = "."
):
    print(service.explain_blame(file, line_start, line_end, cwd, api_key, model))


# ── github ────────────────────────────────────────────────────────────


def cmd_gh_review_pr(repo_pr: str, gh_token_explicit: str | None, api_key: str, model: str):
    repo, _, num = repo_pr.rpartition("/")
    token = service.resolve_github_token(gh_token_explicit)
    print(f"\n\033[94mReviewing PR #{num} in {repo}\033[0m\n")
    print(service.review_pr(repo, int(num), token, api_key, model))


def cmd_gh_triage(repo: str, max_items: int, gh_token_explicit: str | None, api_key: str, model: str):
    token = service.resolve_github_token(gh_token_explicit)
    print(f"\n\033[94mTriaging open issues in {repo}\033[0m\n")
    print(service.triage_issues(repo, max_items, token, api_key, model))


def cmd_gh_commits(repo: str, max_items: int, gh_token_explicit: str | None, api_key: str, model: str):
    token = service.resolve_github_token(gh_token_explicit)
    print(f"\n\033[94mCommit summary for {repo}\033[0m\n")
    print(service.summarise_commits(repo, max_items, token, api_key, model))


def cmd_gh_pr_description(repo_pr: str, gh_token_explicit: str | None, api_key: str, model: str):
    repo, _, num = repo_pr.rpartition("/")
    token = service.resolve_github_token(gh_token_explicit)
    print(f"\n\033[94mGenerating PR description for #{num} in {repo}\033[0m\n")
    print(service.generate_pr_description_gh(repo, int(num), token, api_key, model))


# ── browse ────────────────────────────────────────────────────────────


def _print_browse_step(task: str, start_url: str, s: BrowseStep):
    if s.action == "start":
        print(f"\033[94mAI Model Coder — browse\033[0m  (model: {s.detail})")
        print(f"Task: {task}")
        print(f"Start: {start_url}\n")
    elif s.action == "loop_detected":
        print(f"\033[93m[loop detected] already visited {s.url}; stopping.\033[0m")
    elif s.action == "blocked":
        print(f"\033[91m[blocked] {s.url} is outside --browse-allow-domain restriction.\033[0m")
    elif s.action == "fetching":
        print(f"\033[96m[{s.detail}] fetching\033[0m {s.url}")
    elif s.action == "fetch_error":
        print(f"\033[91m[fetch error] {s.detail}\033[0m")
    elif s.action == "unparsable":
        print(f"\033[93m[unparsable response, treating as final answer]\033[0m\n{s.detail}")
    elif s.action == "answer":
        print(f"\n\033[92mclaude›\033[0m {s.detail}")
    elif s.action == "navigate":
        print(f"  \033[90m→ navigating: {s.detail}\033[0m")
    elif s.action == "unknown_action":
        print(f"\033[93m[unknown action {s.detail}, stopping]\033[0m")
    elif s.action == "max_steps":
        print("\033[93m[max steps reached without a final answer]\033[0m")


def cmd_browse(
    api_key: str,
    model: str,
    start_url: str,
    task: str,
    max_steps: int = 6,
    allowed_domains: list[str] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
):
    return service.browse_session(
        api_key,
        model,
        start_url,
        task,
        max_steps=max_steps,
        allowed_domains=allowed_domains,
        temperature=temperature,
        max_tokens=max_tokens,
        on_step=lambda s: _print_browse_step(task, start_url, s),
    )
