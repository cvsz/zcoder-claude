"""infrastructure/anthropic_api/wif_gateway.py — WIF HTTP transport
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Real HTTP calls to api.anthropic.com for WIF token exchange and admin
operations. No print().
"""

# mypy: ignore-errors

import json
import urllib.error
import urllib.request

from domain.wif import (
    ADMIN_BASE,
    JWT_BEARER_GRANT,
    OAUTH_TOKEN_ENDPOINT,
    WIFExchangeError,
)
from exceptions import APIError, AuthenticationError, RateLimitError, ZCoderError
from infrastructure.anthropic_api.http_client import CircuitBreaker, retry, urlopen_json

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class WIFCredentialExchanger:
    @retry(max_attempts=3, base_delay=1.0, max_delay=10.0, breaker=_breaker)
    def exchange(
        self,
        federation_rule_id: str,
        organization_id: str,
        service_account_id: str,
        identity_token: str,
        workspace_id: str | None = None,
        token_lifetime_seconds: int | None = None,
    ) -> dict:
        body = {
            "grant_type": JWT_BEARER_GRANT,
            "assertion": identity_token,
            "federation_rule_id": federation_rule_id,
            "organization_id": organization_id,
            "service_account_id": service_account_id,
        }
        if workspace_id:
            body["workspace_id"] = workspace_id
        if token_lifetime_seconds is not None:
            body["token_lifetime_seconds"] = token_lifetime_seconds

        req = urllib.request.Request(
            OAUTH_TOKEN_ENDPOINT,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urlopen_json(req, timeout=30)
        except AuthenticationError as e:
            raise WIFExchangeError(401, e.details.get("body", "")) from None
        except RateLimitError as e:
            raise WIFExchangeError(429, e.details.get("body", "")) from None
        except APIError as e:
            raise WIFExchangeError(e.status_code, e.details.get("body", "")) from None
        except ZCoderError as e:
            raise WIFExchangeError(None, e.details.get("body", "")) from None


class WIFAdminClient:
    def __init__(self, org_admin_oauth_token: str):
        self.org_admin_oauth_token = org_admin_oauth_token

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "authorization": f"Bearer {self.org_admin_oauth_token}",
        }

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(f"{ADMIN_BASE}{path}", headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{ADMIN_BASE}{path}",
            data=json.dumps(payload).encode(),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def create_service_account(self, name: str) -> dict:
        return self._post("/service_accounts", {"name": name})

    def list_service_accounts(self) -> dict:
        return self._get("/service_accounts")

    def create_federation_issuer(self, name: str, issuer_url: str, jwks: dict | None = None) -> dict:
        payload = {"name": name, "issuer_url": issuer_url, "jwks": jwks or {"type": "discovery"}}
        return self._post("/federation_issuers", payload)

    def list_federation_issuers(self) -> dict:
        return self._get("/federation_issuers")

    def create_federation_rule(
        self,
        name: str,
        issuer_id: str,
        service_account_id: str,
        match: dict,
        oauth_scope: str | None = None,
        token_lifetime_seconds: int | None = None,
    ) -> dict:
        payload = {
            "name": name,
            "issuer_id": issuer_id,
            "service_account_id": service_account_id,
            "match": match,
        }
        if oauth_scope is not None:
            payload["oauth_scope"] = oauth_scope
        if token_lifetime_seconds is not None:
            payload["token_lifetime_seconds"] = token_lifetime_seconds
        return self._post("/federation_rules", payload)

    def list_federation_rules(self) -> dict:
        return self._get("/federation_rules")
