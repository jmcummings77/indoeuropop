# Agents

Shared agent assets for IndoEuroPop.

## Layout

- `commands/`: slash-command workflow instructions adapted for this Python
  research package.
- `rules/`: repository coding, testing, data, and documentation rules.
- `agent-config.default.json`: default provider/model settings for local
  workflow scripts.
- `settings.json`: shared plugin/tool settings.
- `settings.local.json`: local-only overrides and permissions, ignored by Git.
- `worktrees.json`: fresh-worktree bootstrap commands.

This directory intentionally keeps only rules and commands that apply to the
current Python package, CLI, reporting, data-curation, and research workflow.

## Updating

When the repository adds a new language, workflow, CI job, or deployment
target, update both root `AGENTS.md` and the matching rules or commands here.
