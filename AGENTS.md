# Project Agents

IndoEuroPop is a Python research-engineering package for cautious,
reproducible modeling of Indo-European population dynamics and ancient-DNA
target evidence. Agents working in this repository should preserve the
scientific guardrails: no fabricated results, no historical claims beyond the
current evidence, and explicit separation between curation evidence,
simulation diagnostics, and model interpretation.

## Repository Layout

```text
src/indoeuropop/    Python package source, organized by data, models, analysis,
                    simulation, reporting, and orchestration modules.
tests/              Pytest suite. The project expects 100% coverage for
                    logic-bearing code.
docs/               Research-engineering plans, workflows, data schemas,
                    model diagnostics, and validation notes.
curation/           Reviewed target and model-curation inputs. Treat edits as
                    scientific decisions that need evidence.
examples/           Small synthetic/example inputs for CLI smoke paths.
scripts/            External workflow helpers such as qpAdm planning scripts.
data/               Local AADR/qpAdm data. Ignored by Git; do not overwrite
                    without explicit user permission.
results/            Generated local outputs. Ignored by Git unless the user
                    asks to promote an artifact.
.agents/            Shared agent commands, rules, and local workflow config.
```

## Git Branching Model

- The hosted repository currently uses `main` as the integration branch.
- Do not commit directly to `main` unless the user explicitly asks.
- Feature branches should be named `codex/<short-slug>` or
  `<issue-number>-<short-slug>` when an issue exists.
- Pull requests target `main` unless the repository later adopts a dedicated
  `develop` branch.
- Use squash merge for feature PRs unless the user specifies another policy.

If a future release process introduces `develop`, staging branches, or
deployment targets, update this file and the command docs before using release
automation.

## Agentic Workflow

These command docs live in `.agents/commands/` and are intentionally scoped to
this Python research package:

| Command | Role | Purpose |
| --- | --- | --- |
| `/create-issue` | documentation-agent | Draft a GitHub issue from user intent and create it after approval. |
| `/plan-issue` | planning-agent | Analyze a GitHub issue and write a durable plan under `docs/issue-plans/`. |
| `/build-plan` | coding-agent | Implement an approved plan with tests and verification. |
| `/pr` | documentation-agent | Open a PR against `main` from the current branch using the actual diff. |
| `/audit` | review-agent | Perform a read-only repository audit against this file and `.agents/rules/`. |
| `/fix-unit-test-coverage` | coding-agent | Restore 100% coverage by adding or improving tests. |
| `/trim-files` | coding-agent | Split oversized source or test files while preserving public APIs. |

Agent roles are conceptual modes for the same assistant:

- **documentation-agent** writes issues, PR bodies, changelog notes, and
  concise user-facing summaries.
- **planning-agent** reads the codebase, resolves ambiguity, and decomposes
  work into safe implementation steps.
- **coding-agent** implements changes, writes tests, and verifies gates.
- **review-agent** prioritizes bugs, risk, regressions, missing tests, and
  evidence-backed findings.

## GitHub Tooling

Use the authenticated GitHub CLI (`gh`) from the repository root for GitHub
operations: issues, PRs, reviews, status checks, run logs, labels, and API
queries. Run `gh auth status` before GitHub work.

Do not use external connector/app tooling as the primary path unless the user
explicitly requests it. If connector tooling fails, fall back to `gh` before
halting.

## Local Development

Install and synchronize dependencies with `uv`:

```bash
uv sync --all-extras --dev
```

Useful smoke commands:

```bash
uv run indoeuropop demo
uv run indoeuropop refresh-real-pipeline
uv run indoeuropop review-pipeline-readiness \
  --readiness-report-md results/qpadm-rerun/real-pipeline-readiness.md
```

## Verification Gates

For focused iteration, run the narrowest tests and checks that cover the files
you changed:

```bash
uv run black --check <paths>
uv run ruff check <paths>
uv run mypy src tests
uv run pytest <tests>
```

Before handing off substantial code changes, run the full project gate unless
the user asks for a lighter pass:

```bash
uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
uv run black --check .
uv run ruff check .
uv run mypy src tests
```

Never lower coverage thresholds, broaden coverage exclusions, or add ignore
markers around real logic to make the gate pass. Fix coverage with tests or by
extracting testable logic.

## Python Standards

- Target Python `>=3.11`.
- Use `uv` for dependency and virtualenv management.
- Keep runtime dependencies minimal; add a dependency only when it prevents a
  real reinvention problem.
- Use Black formatting, Ruff linting, strict mypy typing, and pytest.
- Document public functions/classes with accurate docstrings.
- Keep source files under 400 lines and tests/docs under 1000 lines unless the
  file is generated, vendored, or a lockfile.
- Prefer small composable functions, typed dataclasses, and explicit validation.
- Keep compatibility re-exports when moving public modules.

## Research And Data Guardrails

- Treat AADR, qpAdm, and curated target files as evidence surfaces, not ground
  truth.
- Do not overwrite local `data/` artifacts unless the user explicitly permits
  it.
- Do not commit real downloaded data or generated `results/` artifacts unless
  the user explicitly asks to promote them.
- Preserve cautious scientific framing in docs and reports.
- Label outputs clearly as synthetic, simulated, observed, derived, or
  review-candidate evidence.
- Before changing simulator structure to improve fit, inspect target curation,
  uncertainty, sample counts, publication keys, and posterior predictive
  residuals.

## Agent Configuration

Default local workflow configuration lives in
`.agents/agent-config.default.json`. Local overrides may be stored in
`.agents/agent-config.local.json` or `.agents/settings.local.json`; those files
are ignored by Git.
