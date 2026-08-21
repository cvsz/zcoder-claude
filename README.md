# zcoder-claude

Claude-first coding and agent CLI with broad support for the Claude API, Claude Code-style workflows, Agent SDK patterns, Managed Agents, MCP, skills, plugins, web/TUI front ends, and developer automation.

## What it can do

- Run prompts against current Claude models, including advanced thinking, effort, streaming, structured output, fallbacks, and cost-aware routing.
- Use coding-agent workflows for repository work, reviews, issue triage, commit summaries, prompt optimization, and multi-agent routing.
- Work with Managed Agents, sessions, budgets, environments, memory stores, GitHub session resources, and resumable/long-running agent flows.
- Use Agent Skills, MCP integrations, tool-use workflows, workspace metadata, enterprise/admin APIs, and compliance/session transcript APIs.
- Launch a terminal UI or browser-based chat console in addition to the standard CLI.
- Track local usage metrics and expose operational/debugging helpers for development and automation.

## Quick start

```bash
python main.py -p "Explain this repository"
python main.py --model claude-sonnet-5 -p "Review this code"
python main.py --tui
make build && make start
```

## Documentation

- [`COMMAND.md`](COMMAND.md) — full command and capability reference
- [`CHANGELOG.md`](CHANGELOG.md) — release history
- [`ROADMAP.md`](ROADMAP.md) — planned work and capability gaps
- [`IMPLEMENTATION_CHECKLIST.md`](IMPLEMENTATION_CHECKLIST.md) — implementation/audit tracking
- [`docs/`](docs/) — detailed upgrade and feature notes

## Current release

**v1.41.0 — Claude 2026-08-21 Upgrade Alignment**

The project currently covers Claude model/runtime features, Agent Skills, Managed Agents, compliance/session APIs, enterprise administration, web/TUI interfaces, GitHub workflows, prompt tooling, and usage metrics.
