# Plan A GitHub Issue (`/plan-issue`)

You are the planning-agent. Analyze a GitHub issue and write a durable,
implementation-ready plan.

## Arguments

`$ARGUMENTS`

- Required issue number unless it can be inferred from the current branch.

## Workflow

1. Run `gh auth status`.
2. Fetch the issue with `gh issue view <number> --json number,title,body,url`.
3. Read `AGENTS.md`, `.agents/rules/*.mdc`, and relevant source/docs.
4. Decompose the work into small implementation steps.
5. Write `docs/issue-plans/<number>-<slug>.md` with:
   - issue metadata;
   - goal;
   - implementation plan;
   - test plan;
   - risks and scientific/data caveats.
6. Append or update a concise `## Implementation Plan` section on the GitHub
   issue after user approval.

Plans should prefer existing package patterns, avoid speculative refactors, and
call out when real data or generated artifacts must not be committed.
