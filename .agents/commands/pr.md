# Open A Pull Request (`/pr`)

You are the documentation-agent. Open a GitHub pull request for the current
branch against `main`, using the actual diff as the source of truth.

## Arguments

`$ARGUMENTS`

- Optional target branch; default is `main`.

## Workflow

1. Run `gh auth status`.
2. Confirm the current branch is not `main` and is not detached.
3. Run or confirm required local verification:

   ```bash
   uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
   uv run black --check .
   uv run ruff check .
   uv run mypy src tests
   ```

4. Push the branch with a non-destructive `git push -u origin HEAD`.
5. Collect diff evidence with `git diff --stat origin/main...HEAD` and targeted
   `git diff` reads.
6. Create a PR body with:
   - summary;
   - key changes;
   - testing commands actually run;
   - data/scientific caveats;
   - follow-up work.
7. Create the PR with `gh pr create`.

Do not merge from this command. Do not claim tests were run unless they were.
