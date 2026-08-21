"""interfaces/cli/commands/wif_commands.py — CLI presentation for WIF
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/wif_service.py.
"""

from application import wif_service as service


def cmd_wif_status():
    print("\\n\\033[94mWorkload Identity Federation — environment status\\033[0m\\n")
    status = service.get_wif_status()
    for var, state in status.items():
        if var in ("active",):
            continue
        display = "\\033[92mset\\033[0m" if state == "set" else "\\033[90mnot set\\033[0m"
        print(f"  {var:<32} {display}")
    print()
    if status.get("active"):
        print("\\033[92m✓ Federation would activate\\033[0m (all required vars present)")
    else:
        print(
            "\\033[93mℹ Federation would NOT activate\\033[0m — falls through to a "
            "static API key. Required: ANTHROPIC_FEDERATION_RULE_ID, "
            "ANTHROPIC_ORGANIZATION_ID, ANTHROPIC_SERVICE_ACCOUNT_ID, and one of "
            "ANTHROPIC_IDENTITY_TOKEN_FILE / ANTHROPIC_IDENTITY_TOKEN."
        )
    return status


def cmd_wif_exchange_token():
    result = service.exchange_token()
    if not result:
        print(
            "\\033[91m✗ WIF is not fully configured in the environment.\\033[0m "
            "Run --wif-status to see which variables are missing."
        )
        return None
    access_token = result.get("access_token", "")
    preview = f"{access_token[:14]}...{access_token[-4:]}" if len(access_token) > 20 else "***"
    print(
        f"\\033[92m✓ Exchanged for a Claude API access token\\033[0m  "
        f"token={preview}  expires_in={result.get('expires_in')}s  "
        f"scope={result.get('scope')}"
    )
    return result


def cmd_wif_create_service_account(name: str, org_admin_token: str):
    data = service.create_service_account(name, org_admin_token)
    if "error" in data:
        print(f"\\033[91m✗ Failed to create service account: {data['error']}\\033[0m")
        return data
    print(f"\\033[92m✓ service account created\\033[0m  id={data.get('id', '?')}  name={name}")
    return data


def cmd_wif_list_service_accounts(org_admin_token: str):
    data = service.list_service_accounts(org_admin_token)
    if "error" in data:
        print(f"\\033[91m✗ Failed to list service accounts: {data['error']}\\033[0m")
        return data
    for sa in data.get("data", []):
        print(f"  {sa.get('id', '?')}  {sa.get('name', '')}")
    return data


def cmd_wif_create_issuer(name: str, issuer_url: str, org_admin_token: str):
    data = service.create_federation_issuer(name, issuer_url, org_admin_token)
    if "error" in data:
        print(f"\\033[91m✗ Failed to create federation issuer: {data['error']}\\033[0m")
        return data
    print(f"\\033[92m✓ federation issuer created\\033[0m  id={data.get('id', '?')}  name={name}")
    return data


def cmd_wif_list_issuers(org_admin_token: str):
    data = service.list_federation_issuers(org_admin_token)
    if "error" in data:
        print(f"\\033[91m✗ Failed to list federation issuers: {data['error']}\\033[0m")
        return data
    for fi in data.get("data", []):
        print(f"  {fi.get('id', '?')}  {fi.get('name', '')}  {fi.get('issuer_url', '')}")
    return data


def cmd_wif_create_rule(
    name: str, issuer_id: str, service_account_id: str, subject_prefix: str, org_admin_token: str
):
    data = service.create_federation_rule(
        name,
        issuer_id,
        service_account_id,
        subject_prefix,
        org_admin_token,
    )
    if "error" in data:
        print(f"\\033[91m✗ Failed to create federation rule: {data['error']}\\033[0m")
        return data
    print(f"\\033[92m✓ federation rule created\\033[0m  id={data.get('id', '?')}  name={name}")
    return data


def cmd_wif_list_rules(org_admin_token: str):
    data = service.list_federation_rules(org_admin_token)
    if "error" in data:
        print(f"\\033[91m✗ Failed to list federation rules: {data['error']}\\033[0m")
        return data
    for fr in data.get("data", []):
        print(f"  {fr.get('id', '?')}  {fr.get('name', '')}")
    return data
