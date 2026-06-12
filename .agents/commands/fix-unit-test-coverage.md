# Fix Unit Test Coverage (`/fix-unit-test-coverage`)

You are the coding-agent. Restore the repository's 100% coverage gate without
gaming the metrics.

## Arguments

`$ARGUMENTS`

- Optional path, module, or failing coverage output.

## Workflow

1. Run the relevant focused pytest command or the full coverage gate if the
   user supplied a full failure:

   ```bash
   uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
   ```

2. Identify uncovered executable logic.
3. Add tests for public behavior, edge cases, validation errors, and branch
   conditions.
4. Refactor hard-to-test code into pure helpers only when it improves clarity.
5. Re-run focused tests, then the full coverage gate.

Never lower `fail_under`, alter coverage include/exclude settings, or add
ignore markers around real logic.
