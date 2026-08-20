import pytest

from domain.agents.session_resources import GitHubRepositoryResource


def test_github_resource_builds_branch_checkout_and_redacts_token():
    resource = GitHubRepositoryResource(
        url="https://github.com/example/repo",
        authorization_token="secret-token",
        mount_path="/workspace/repo",
        branch="main",
    )
    payload = resource.to_api_dict()
    assert payload["authorization_token"] == "secret-token"
    assert payload["checkout"] == {"type": "branch", "name": "main"}
    assert "authorization_token" not in resource.safe_dict()
    assert "secret-token" not in repr(resource.safe_dict())


def test_github_resource_supports_full_commit_sha():
    sha = "a" * 40
    payload = GitHubRepositoryResource(
        url="https://github.com/example/repo",
        authorization_token="token",
        commit_sha=sha,
    ).to_api_dict()
    assert payload["checkout"] == {"type": "commit", "sha": sha}


def test_github_resource_rejects_branch_and_commit_together():
    with pytest.raises(ValueError):
        GitHubRepositoryResource(
            url="https://github.com/example/repo",
            authorization_token="token",
            branch="main",
            commit_sha="a" * 40,
        ).to_api_dict()


def test_github_resource_rejects_non_github_or_relative_mount():
    with pytest.raises(ValueError):
        GitHubRepositoryResource("https://example.com/repo", "token").to_api_dict()
    with pytest.raises(ValueError):
        GitHubRepositoryResource(
            "https://github.com/example/repo", "token", mount_path="relative/path"
        ).to_api_dict()
