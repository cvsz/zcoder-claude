"""Pure Managed Agents session-resource value objects."""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class GitHubRepositoryResource:
    url: str
    authorization_token: str
    mount_path: Optional[str] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None

    def validate(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ValueError("GitHub repository resource URL must be an https://github.com/... URL")
        if not self.authorization_token:
            raise ValueError("GitHub repository resource requires an authorization token")
        if self.branch and self.commit_sha:
            raise ValueError("choose either branch or commit_sha, not both")
        if self.commit_sha and (len(self.commit_sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in self.commit_sha)):
            raise ValueError("commit_sha must be a full 40-character hexadecimal SHA")
        if self.mount_path is not None and not self.mount_path.startswith("/"):
            raise ValueError("mount_path must be absolute")

    def to_api_dict(self) -> dict:
        self.validate()
        data = {
            "type": "github_repository",
            "url": self.url,
            "authorization_token": self.authorization_token,
        }
        if self.mount_path:
            data["mount_path"] = self.mount_path
        if self.branch:
            data["checkout"] = {"type": "branch", "name": self.branch}
        elif self.commit_sha:
            data["checkout"] = {"type": "commit", "sha": self.commit_sha}
        return data

    def safe_dict(self) -> dict:
        """Serializable representation that never exposes credentials."""
        data = {"type": "github_repository", "url": self.url}
        if self.mount_path:
            data["mount_path"] = self.mount_path
        if self.branch:
            data["checkout"] = {"type": "branch", "name": self.branch}
        elif self.commit_sha:
            data["checkout"] = {"type": "commit", "sha": self.commit_sha}
        return data
