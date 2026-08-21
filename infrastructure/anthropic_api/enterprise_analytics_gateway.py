"""Claude Enterprise Analytics API transport adapter.

Uses an Analytics API key (`read:analytics`) and the
/v1/organizations/analytics/* endpoint family.  This is intentionally
separate from the Admin API / Claude Code Analytics client because the key
types are not interchangeable.
"""

import json
import urllib.parse
import urllib.request

from domain.enterprise_analytics import build_analytics_query

BASE_URL = "https://api.anthropic.com/v1/organizations/analytics"


class EnterpriseAnalyticsGateway:
    def __init__(self, api_key: str, timeout: int = 60):
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "zcoder-claude/enterprise-analytics",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def user_activity(self, **query) -> dict:
        return self._get("/users", build_analytics_query(**query))

    def summaries(self, **query) -> dict:
        return self._get("/summaries", build_analytics_query(**query))

    def chat_projects(self, **query) -> dict:
        return self._get("/apps/chat/projects", build_analytics_query(**query))

    def skill_usage(self, **query) -> dict:
        return self._get("/skills", build_analytics_query(**query))

    def connector_usage(self, **query) -> dict:
        return self._get("/connectors", build_analytics_query(**query))

    def plugin_usage(self, **query) -> dict:
        return self._get("/plugins", build_analytics_query(**query))

    def artifact_activity(self, **query) -> dict:
        return self._get("/artifacts", build_analytics_query(**query))

    def cost_report(self, **query) -> dict:
        return self._get("/cost_report", build_analytics_query(**query))

    def user_cost_report(self, **query) -> dict:
        return self._get("/user_cost_report", build_analytics_query(**query))
