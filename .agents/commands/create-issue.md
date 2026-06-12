# Create A GitHub Issue (`/create-issue`)

You are the documentation-agent. Draft a complete GitHub issue from the user's
description and create it only after the user approves the draft.

## Arguments

`$ARGUMENTS`

- Description of the feature, bug, research task, or maintenance task.
- Optional label hints such as `bug`, `feature`, `docs`, `research`, or
  `maintenance`.

## Workflow

1. Run `gh auth status`.
2. Inspect relevant repo docs or files if the request needs evidence.
3. Draft the issue with:
   - title;
   - problem / motivation;
   - proposed scope;
   - acceptance criteria;
   - verification expectations;
   - scientific/data caveats when relevant.
4. Ask for confirmation before creating the issue.
5. After approval, create it with `gh issue create`.

Do not create issues for vague work without enough context; ask one focused
question when needed.
