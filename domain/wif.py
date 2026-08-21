"""domain/wif.py — Workload Identity Federation domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for WIF. No I/O, no print(), no `import
anthropic` — those belong to infrastructure/.
"""

import os
from pathlib import Path

OAUTH_TOKEN_ENDPOINT = "https://api.anthropic.com/v1/oauth/token"
ADMIN_BASE = "https://api.anthropic.com/v1/organizations"
JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"

WIF_ENV_VARS = (
    "ANTHROPIC_FEDERATION_RULE_ID",
    "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_SERVICE_ACCOUNT_ID",
    "ANTHROPIC_WORKSPACE_ID",
    "ANTHROPIC_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_IDENTITY_TOKEN",
)


class WIFExchangeError(Exception):
    def __init__(self, status: int | None, body: str):
        self.status = status
        self.body = body
        super().__init__(f"WIF token exchange failed: HTTP {status}")


def resolve_wif_env(env: dict | None = None) -> dict | None:
    env = env if env is not None else os.environ
    rule_id = env.get("ANTHROPIC_FEDERATION_RULE_ID")
    org_id = env.get("ANTHROPIC_ORGANIZATION_ID")
    svc_account_id = env.get("ANTHROPIC_SERVICE_ACCOUNT_ID")
    if not (rule_id and org_id and svc_account_id):
        return None

    identity_token = None
    token_file = env.get("ANTHROPIC_IDENTITY_TOKEN_FILE")
    if token_file:
        try:
            identity_token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            return None
    if identity_token is None:
        identity_token = env.get("ANTHROPIC_IDENTITY_TOKEN")
    if not identity_token:
        return None

    return {
        "federation_rule_id": rule_id,
        "organization_id": org_id,
        "service_account_id": svc_account_id,
        "workspace_id": env.get("ANTHROPIC_WORKSPACE_ID"),
        "identity_token": identity_token,
    }
