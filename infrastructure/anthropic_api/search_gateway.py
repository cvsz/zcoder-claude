"""
# mypy: ignore-errors
infrastructure/anthropic_api/search_gateway.py — Web Search & Web Fetch
(Anthropic server tools) live API adapter
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_search.py. SearchCoder itself was
already print-free — only cmd_* had print(), now in
interfaces/cli/commands/tools_commands.py.
"""

import anthropic

WEB_SEARCH_TOOL = {"type": "web_search_20260318", "name": "web_search"}
WEB_FETCH_TOOL = {"type": "web_fetch_20260318", "name": "web_fetch"}


class SearchCoder:
    """Claude with web search and fetch tools."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_tokens: int = 4096):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def search(
        self,
        prompt: str,
        system: str | None = None,
        web_search: bool = True,
        web_fetch: bool = False,
        max_searches: int = 5,
        show_citations: bool = True,
        response_inclusion: str | None = None,
    ) -> dict:
        """Run prompt with web search / fetch tools enabled."""
        tools = []
        if web_search:
            t = dict(WEB_SEARCH_TOOL)
            t["max_uses"] = max_searches
            if response_inclusion is not None:
                t["response_inclusion"] = response_inclusion
            tools.append(t)
        if web_fetch:
            t = dict(WEB_FETCH_TOOL)
            if response_inclusion is not None:
                t["response_inclusion"] = response_inclusion
            tools.append(t)

        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
        )
        if system:
            kwargs["system"] = system

        resp = self.client.messages.create(**kwargs)

        response_text = ""
        citations = []
        searches_made = 0

        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                response_text += block.text
            elif btype == "server_tool_use" and block.name == "web_search":
                searches_made += 1
            elif btype == "web_search_tool_result":
                for item in getattr(block, "content", []):
                    if getattr(item, "type", "") == "web_search_result":
                        citations.append(
                            {"title": getattr(item, "title", ""), "url": getattr(item, "url", "")}
                        )

        usage = resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else {}

        return {
            "response": response_text,
            "citations": citations,
            "searches": searches_made,
            "usage": usage,
            "stop_reason": resp.stop_reason,
        }

    def fetch_and_summarise(self, url: str, instruction: str = "") -> str:
        """Fetch a URL and summarise / answer from its content."""
        prompt = f"Please fetch and read this URL, then {instruction or 'summarise the key points'}: {url}"
        result = self.search(prompt, web_search=False, web_fetch=True)
        return result["response"]
