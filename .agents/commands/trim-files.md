# Trim Oversized Files (`/trim-files`)

You are the coding-agent. Split oversized hand-written files into cohesive
modules while preserving behavior and public imports.

## Arguments

`$ARGUMENTS`

- Optional path or scope.
- Optional maximum number of files to process.

## Discovery

Source files over 400 lines:

```bash
git ls-files 'src/**/*.py' 'scripts/**/*.py' \
  | xargs wc -l 2>/dev/null \
  | awk '$1 > 400 && $2 != "total" {print}' \
  | sort -n
```

Tests and docs over 1000 lines:

```bash
git ls-files 'tests/**/*.py' 'docs/**/*.md' \
  | xargs wc -l 2>/dev/null \
  | awk '$1 > 1000 && $2 != "total" {print}' \
  | sort -n
```

## Refactoring Rules

- Split by responsibility, not by arbitrary line count.
- Prefer modules such as `*_models.py`, `*_report.py`, `*_cli.py`, and
  feature-specific helpers.
- Preserve compatibility exports in `_api_*.py`, package `__init__.py`, or
  root alias maps when moving public imports.
- Move or add tests with the extracted code.
- Run focused tests during the split and the full gate before handoff.
