# Implement An Approved Plan (`/build-plan`)

You are the coding-agent. Implement an approved plan from `docs/issue-plans/`
or from the referenced GitHub issue. Keep the diff focused, tested, and
consistent with `AGENTS.md` and `.agents/rules/`.

## Arguments

`$ARGUMENTS`

- Optional issue number, for example `42` or `#42`.
- Optional `--continue-to-pr`: after passing local verification, continue to
  `/pr`.

## Workflow

1. Resolve the issue number from arguments or the current branch name.
2. Read the plan from `docs/issue-plans/<issue>-*.md`. If none exists, inspect
   the GitHub issue body/comments with `gh issue view` and `gh api`.
3. Verify branch and working tree state with `git status --short`.
4. Read relevant source files before editing.
5. Implement the plan in small steps, preserving public APIs and scientific
   guardrails.
6. Add or update tests for every logic-bearing change.
7. Run focused checks while iterating.
8. Before handoff, run the full gate unless the user requested a lighter pass:

   ```bash
   uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
   uv run black --check .
   uv run ruff check .
   uv run mypy src tests
   ```

9. Summarize changed files, verification, and any residual risk.

Never lower coverage, add ignore markers for real logic, or overwrite local
`data/` files without explicit permission.
