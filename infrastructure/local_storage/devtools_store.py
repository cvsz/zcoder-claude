"""
infrastructure/local_storage/devtools_store.py — git subprocess execution
and local file I/O for the Dev-tool Integrations bounded context
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

Extracted from claude_git.py. Subprocess execution of the local `git`
binary and reading/writing local files are local-machine I/O, not an
HTTP call — same bucket as `infrastructure/local_storage/code_agent_store.py`'s
subprocess use for Claude Code sessions (see that module's docstring for
the precedent this follows).
"""

import subprocess
from pathlib import Path


def run_git(cmd: str, cwd: str = ".") -> str:
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip() or r.stderr.strip()


def get_staged_diff(cwd: str = ".") -> str:
    diff = run_git("git diff --cached", cwd)
    return diff or run_git("git diff HEAD", cwd) or "(no changes detected)"


def get_commit_log(base: str, head: str, cwd: str = ".") -> str:
    return run_git(f"git log {base}..{head} --oneline", cwd)


def get_diff_stat(base: str, head: str, cwd: str = ".") -> str:
    return run_git(f"git diff {base}..{head} --stat", cwd)


def get_changelog_log(since_tag: str, cwd: str = ".") -> str:
    return run_git(f"git log {since_tag}..HEAD --oneline", cwd)


def get_file_blame_log(file: str, cwd: str = ".") -> str:
    return run_git(f"git log --oneline {file}", cwd)


def read_file_lines(cwd: str, file: str, line_start: int, line_end: int) -> str:
    """Returns the requested line range joined with single newlines, or a
    placeholder string on any read failure.

    v1.44.0 fix: the original fed readlines() straight into "\\n".join(),
    keeping each line's own trailing newline AND inserting the join
    separator — doubled newlines between requested lines."""
    try:
        with open(f"{cwd}/{file}") as f:
            lines = f.readlines()[line_start - 1 : line_end]
        return "\n".join(line.rstrip("\n") for line in lines)
    except Exception:
        return "(could not read file)"


def commit_with_message(message: str, cwd: str = ".") -> tuple[bool, str]:
    """Runs `git commit -m <message>`. Returns (success, status-message).

    v1.44.0 fix: on failure, the human-readable status is now returned
    regardless of which stream git wrote it to. The original always
    returned result.stderr, but git writes some failure messages (notably
    "nothing to commit") to stdout — leaving callers with an empty string
    on that failure path. Success still returns ""."""
    result = subprocess.run(["git", "commit", "-m", message], cwd=cwd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.strip() or result.stdout.strip()


def write_text_file(path: str, text: str) -> None:
    Path(path).write_text(text)
