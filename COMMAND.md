# AI Model Coder CLI — Full Command Reference

This file is the long-form command and capability reference for `zcoder-claude`.

The historical README from commit `01a4712` remains the source for the detailed command catalog and release notes. The project landing page is intentionally kept short in `README.md`.

## Core command groups

- Claude model execution, streaming, structured output, thinking/effort, fallback chains, and cost-aware routing
- Managed Agents: create/get/list/update, sessions, budgets, environments, memories, GitHub repository resources, and resumable flows
- Claude Enterprise/Admin APIs: organization members, invites, groups, roles, analytics, compliance/session transcripts, API-key operations, and workspace metadata
- Agent Skills and MCP integrations
- GitHub developer workflows: PR review, issue triage, commit summaries, and PR-description generation
- Prompt optimization, scoring, A/B testing, prompt library, multi-agent routing, and advisor workflows
- Files, batch, cache, search, vision/PDF, code execution, tool use, sessions, and local memory workflows
- Local metrics, usage export, observability, debugging, and operational helpers
- Textual TUI and browser-based web console

## Common examples

```bash
python main.py -p "Explain this repository"
python main.py --model claude-sonnet-5 -p "Review this code"
python main.py --model claude-opus-5 --fast-mode -p "Solve this task"
python main.py --thinking --model claude-sonnet-5 -p "Reason through this"
python main.py --tui
make build && make start
```

### GitHub workflows

```bash
python main.py --gh-review-pr anthropics/claude-code/42
python main.py --gh-triage-issues anthropics/claude-code --gh-max-items 10
python main.py --gh-summarise-commits anthropics/claude-code
python main.py --gh-pr-description anthropics/claude-code/42
```

### Prompt tooling and routing

```bash
python main.py --route "why is this query slow" --route-explain
python main.py --route-list
python main.py --optimize "make me a todo app"
python main.py --score-prompt "make me a todo app"
python main.py --ab-test --prompt "variant A" --ab-prompt-b "variant B" --ab-task "summarize a support ticket"
python main.py --prompt-lib-list
```

### Usage metrics

```bash
python main.py --metrics-show --metrics-today
python main.py --metrics-export usage.json
python main.py --metrics-clear
```

### Managed Agents and memory

```bash
python main.py --agent-memory-stores-list --agent-memory-stores-include-archived
python main.py --agent-memory-create memstore_01AbCD --agent-memory-path "/preferences/formatting.md" --agent-memory-content "Always use tabs, not spaces."
```

## Detailed release history

See:

- [`CHANGELOG.md`](CHANGELOG.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`IMPLEMENTATION_CHECKLIST.md`](IMPLEMENTATION_CHECKLIST.md)
- [`docs/`](docs/)

For a concise overview, see [`README.md`](README.md).
