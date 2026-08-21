"""tests/test_devtools_store.py

Covers infrastructure/local_storage/devtools_store.py — git subprocess
execution and local file I/O for the Dev-tool Integrations bounded
context, extracted 2026-08-20 (Phase D, Context #8). Uses real `git`
subprocess calls against throwaway repos in tmp_path — no mocking of
subprocess itself, since exercising the real git binary is the point
(this is exactly the kind of local-process I/O the domain/infra split
exists to isolate, and mocking it away would test nothing).
"""
import subprocess

import pytest

import infrastructure.local_storage.devtools_store as store


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, shell=True, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git init -q", repo)
    _run('git config user.email "t@t.com"', repo)
    _run('git config user.name "t"', repo)
    _run("git config tag.gpgsign false", repo)
    (repo / "a.txt").write_text("hello\n")
    _run("git add a.txt", repo)
    _run('git commit -q -m "init"', repo)
    return repo


def test_run_git_executes_real_command(git_repo):
    out = store.run_git("git log --oneline", str(git_repo))
    assert "init" in out


def test_get_staged_diff_no_changes(git_repo):
    assert store.get_staged_diff(str(git_repo)) == "(no changes detected)"


def test_get_staged_diff_with_staged_changes(git_repo):
    (git_repo / "a.txt").write_text("hello\nworld\n")
    _run("git add a.txt", git_repo)
    diff = store.get_staged_diff(str(git_repo))
    assert "+world" in diff


def test_get_commit_log_between_refs(git_repo):
    (git_repo / "b.txt").write_text("second\n")
    _run("git add b.txt", git_repo)
    _run('git commit -q -m "second commit"', git_repo)
    log = store.get_commit_log("HEAD~1", "HEAD", str(git_repo))
    assert "second commit" in log


def test_get_diff_stat_between_refs(git_repo):
    (git_repo / "b.txt").write_text("second\n")
    _run("git add b.txt", git_repo)
    _run('git commit -q -m "second commit"', git_repo)
    stat = store.get_diff_stat("HEAD~1", "HEAD", str(git_repo))
    assert "b.txt" in stat


def test_get_changelog_log_since_tag(git_repo):
    _run("git tag v1.0", git_repo)
    (git_repo / "c.txt").write_text("third\n")
    _run("git add c.txt", git_repo)
    _run('git commit -q -m "third commit"', git_repo)
    log = store.get_changelog_log("v1.0", str(git_repo))
    assert "third commit" in log


def test_get_changelog_log_empty_when_no_new_commits(git_repo):
    _run("git tag v1.0", git_repo)
    assert store.get_changelog_log("v1.0", str(git_repo)) == ""


def test_get_file_blame_log(git_repo):
    log = store.get_file_blame_log("a.txt", str(git_repo))
    assert "init" in log


def test_read_file_lines_returns_requested_range(git_repo):
    (git_repo / "multi.txt").write_text("line1\nline2\nline3\nline4\n")
    result = store.read_file_lines(str(git_repo), "multi.txt", 2, 3)
    # "\n".join() of readlines() keeps each line's own trailing "\n" *and*
    # inserts the join separator between them — a double newline between
    # entries. This is claude_git.py's original behavior verbatim
    # (open(...).readlines()[start-1:end] fed straight into "\n".join()),
    # not something this migration changed.
    assert result == "line2\n\nline3\n"


def test_read_file_lines_missing_file_returns_placeholder(git_repo):
    result = store.read_file_lines(str(git_repo), "nope.txt", 1, 1)
    assert result == "(could not read file)"


def test_commit_with_message_success(git_repo):
    (git_repo / "a.txt").write_text("hello\nworld\n")
    _run("git add a.txt", git_repo)
    success, err = store.commit_with_message("test commit", str(git_repo))
    assert success is True


def test_commit_with_message_failure_when_nothing_staged(git_repo):
    success, err = store.commit_with_message("empty commit", str(git_repo))
    assert success is False
    # git's "nothing to commit" message goes to stdout, not stderr, so
    # `err` (== result.stderr) is empty on this particular failure path —
    # this matches claude_git.py's original commit_with_message() verbatim
    # (it always returned result.stderr, whether or not stderr was
    # actually populated for a given failure reason); not something this
    # migration changed or should "fix" silently.
    assert err == ""


def test_write_text_file(tmp_path):
    out = tmp_path / "changelog.md"
    store.write_text_file(str(out), "# Changelog\n")
    assert out.read_text() == "# Changelog\n"
