# zcoder-claude

Claude-first coding and agent CLI for model execution, repository automation, Managed Agents, enterprise APIs, skills/MCP, and local developer tooling.

## What we can do

- Run Claude models with streaming, structured output, thinking/effort, fallbacks, and cost-aware routing.
- Use coding-agent workflows for repository review, issue triage, commit summaries, and PR descriptions.
- Create and operate Managed Agents, sessions, budgets, environments, memories, and GitHub session resources.
- Work with Agent Skills, MCP, tool use, files, batch, cache, search, vision/PDF, and code-execution workflows.
- Use Claude Enterprise/Admin and Compliance APIs, including users, groups, roles, analytics, session transcripts, and workspace metadata.
- Optimize and score prompts, run A/B tests, use prompt libraries, and route work across multiple agents.
- Launch a Textual TUI or browser web console.
- Track usage metrics and observability/debugging data locally.

## Quick start

```bash
python main.py -p "Explain this repository"
python main.py --model claude-sonnet-5 -p "Review this code"
python main.py --tui
make build && make start
```

## Docs

- [`COMMAND.md`](COMMAND.md) — command and capability reference
- [`CHANGELOG.md`](CHANGELOG.md) — release history
- [`ROADMAP.md`](ROADMAP.md) — planned work
- [`IMPLEMENTATION_CHECKLIST.md`](IMPLEMENTATION_CHECKLIST.md) — implementation tracking
- [`docs/`](docs/) — detailed feature and upgrade notes

**Current release:** v1.41.0
