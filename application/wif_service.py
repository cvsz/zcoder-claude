"""application/wif_service.py — use-case layer for WIF
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/wif.py + infrastructure/anthropic_api/wif_gateway.py
— no print() of its own.
"""
# mypy: ignore-errors

import os

from domain.wif import WIF_ENV_VARS, WIFExchangeError, resolve_wif_env
from infrastructure.anthropic_api.wif_gateway import (
    WIFAdminClient,
    WIFCredentialExchanger,
)


def get_wif_status(env: dict | None = None) -> dict:
    env = env or os.environ
    config = resolve_wif_env(env)
    status = {}
    for var in WIF_ENV_VARS:
        status[var] = "set" if env.get(var) else "not set"
    status["active"] = bool(config)
    return status


def exchange_token(env: dict | None = None) -> dict | None:
    config = resolve_wif_env(env or os.environ)
    if not config:
        return None
    exchanger = WIFCredentialExchanger()
    try:
        return exchanger.exchange(
            federation_rule_id=config["federation_rule_id"],
            organization_id=config["organization_id"],
            service_account_id=config["service_account_id"],
            identity_token=config["identity_token"],
            workspace_id=config.get("workspace_id"),
        )
    except WIFExchangeError:
        return None


def create_service_account(name: str, org_admin_token: str) -> dict:
    return WIFAdminClient(org_admin_token).create_service_account(name)


def list_service_accounts(org_admin_token: str) -> dict:
    return WIFAdminClient(org_admin_token).list_service_accounts()


def create_federation_issuer(name: str, issuer_url: str, org_admin_token: str) -> dict:
    return WIFAdminClient(org_admin_token).create_federation_issuer(name, issuer_url)


def list_federation_issuers(org_admin_token: str) -> dict:
    return WIFAdminClient(org_admin_token).list_federation_issuers()


def create_federation_rule(
    name: str, issuer_id: str, service_account_id: str, subject_prefix: str, org_admin_token: str
) -> dict:
    client = WIFAdminClient(org_admin_token)
    match = {"subject_prefix": subject_prefix}
    return client.create_federation_rule(name, issuer_id, service_account_id, match)


def list_federation_rules(org_admin_token: str) -> dict:
    return WIFAdminClient(org_admin_token).list_federation_rules()
