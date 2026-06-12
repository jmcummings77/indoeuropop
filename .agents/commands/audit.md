# Repository Audit (`/audit`)

You are the review-agent. Perform a read-only audit against `AGENTS.md`,
`.agents/rules/`, `pyproject.toml`, docs, tests, and relevant source files.

## Arguments

`$ARGUMENTS`

- Optional scope such as `testing`, `data pipeline`, `public API`, `docs`, or
  a path prefix.

## Workflow

1. Resolve the requested scope.
2. Read `AGENTS.md` and applicable `.agents/rules/*.mdc`.
3. Gather evidence with `rg`, `rg --files`, `git ls-files`, `sed`, and focused
   file reads.
4. Report findings first, ordered by severity, with file/line references.
5. Mark areas as `Unknown` when evidence is insufficient.
6. Do not edit files, create issues, commit, push, or change configuration
   unless the user separately asks for follow-up work.

Prioritize real risks: broken workflows, untested logic, stale docs, data-loss
risks, misleading scientific claims, and public API regressions.
