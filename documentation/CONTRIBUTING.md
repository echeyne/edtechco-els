# Contributing Guide

## Development Setup

### Prerequisites

- Python 3.13+
- Node.js 20+
- pnpm 9+
- Docker (for CDK Lambda bundling)
- AWS CLI v2 (for deployment and manual testing)

### Initial Setup

```bash
# Clone the repo
git clone <repository-url>
cd els-pipeline

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Node.js dependencies
pnpm install

# Environment variables
cp .env.example .env
# Edit .env with your values
```

### Running Locally

```bash
# Python tests (no AWS required)
pytest tests/ -v

# Node.js tests
pnpm test

# Build all packages
pnpm build

# Run a specific frontend in dev mode
pnpm --filter @els/frontend dev
pnpm --filter @els/planning-frontend dev

# Run a specific API in dev mode
pnpm --filter @els/api dev
pnpm --filter @els/planning-api dev
```

## Project Structure

The project is a hybrid monorepo:

- **Python** (`src/els_pipeline/`, `tests/`): Managed by `pyproject.toml`. The core pipeline logic.
- **Node.js** (`packages/`): Managed by pnpm workspaces + Turborepo. Web applications and APIs.
- **Infrastructure** (`infra/cdk/`): AWS CDK in TypeScript.

### Package Dependency Graph

```
@els/shared ──→ @els/api ──────────→ @els/frontend
            └──→ @els/planning-api ──→ @els/planning-frontend

@els/landing-site   (standalone — does not depend on @els/shared)
```

`@els/shared` must be built before any dependent package. Turborepo handles this automatically via `pnpm build`. Note that `pnpm test` depends on `build` (see `turbo.json`), so a broken build blocks the tests.

`@els/shared`'s `types.ts` is the TypeScript mirror of the Pydantic models in `src/els_pipeline/models.py`. **Changing the data model means changing both** — they are not generated from a single source.

## Code Style

### Python

- Follow PEP 8
- Use type hints for all function signatures
- Use Pydantic models for data validation
- Docstrings for public functions (Google style)
- Keep Lambda handlers thin — delegate to module functions

### TypeScript

- Strict TypeScript (`strict: true`)
- Use Zod for runtime validation in APIs
- Shared types go in `@els/shared`
- Use Hono's typed context for API routes

### General

- Keep functions focused and small
- Prefer explicit over implicit
- No unused imports or variables
- Meaningful variable and function names

## Testing Requirements

All changes should include appropriate tests:

- **Pipeline modules**: Property-based test (Hypothesis) + integration test (moto)
- **API routes**: vitest with mocked database
- **Frontend components**: vitest + Testing Library
- **Infrastructure**: Verify deployment works in dev before merging

See [TESTING.md](TESTING.md) for the full testing guide.

### Running Tests Before Committing

```bash
# Python
pytest tests/ -v

# Node.js
pnpm test

# Type checking
pnpm typecheck
```

## Making Changes

### Pipeline Changes

1. Modify the module in `src/els_pipeline/`
2. Update or add tests in `tests/`
3. Run `pytest tests/ -v` to verify
4. If the change affects Lambda handlers, test deployment in dev

### Detector / Parser Changes — read this first

`detector.py` and `parser.py` are held to a stricter rule than the rest of the pipeline: **they are LLM-driven, not rule-driven.** Document-structure decisions (how to classify a level, build a code, handle age-band columns, strip a structural label) belong in the **prompt**, stated as general principles — not in Python regexes or per-state branches.

The history here matters: the golden states (CA, AZ, CO, TX) had each been made to pass by adding targeted per-state Python logic that scored well on the goldens and **did not generalize**. The June 2026 LLM-first migration deleted that logic and moved each rule into the prompt. So:

1. **Prefer fixing the prompt.** A rule that helps every document belongs there.
2. **Fall back to Python only for genuinely document-agnostic post-processing** — JSON extraction, schema validation, ID derivation from already-clean fields, cross-chunk reconciliation.
3. **Never loosen the eval matchers or edit goldens** to paper over a generalization gap. Fix the golden data and canonicalize the model output instead.
4. **A new per-state regex or branch is a regression in disguise, even if it raises a golden score.** Flag it rather than adding it.

Grade the change with the eval suites, not just `pytest` — and check it against a held-out state (Nevada is the current canary) to prove it generalizes:

```bash
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_parser --detection-dir outputs/MM-DD-YY
```

Full rules, and the list of helpers that were deliberately removed, are in [CLAUDE.md](../CLAUDE.md).

### API Changes

1. Modify routes in `packages/els-explorer-api/src/routes/` or `packages/planning-api/src/routes/`
2. Update shared types in `packages/shared/src/types.ts` if needed
3. Run `pnpm --filter @els/shared build` then `pnpm --filter @els/api test`
4. Update [API.md](API.md) if endpoints changed

### Frontend Changes

1. Modify components in the relevant frontend package
2. Run `pnpm --filter <package> dev` to preview
3. Run `pnpm --filter <package> test` to verify

### Infrastructure Changes

1. Modify CDK stacks in `infra/cdk/lib/`
2. Run `npx cdk diff <stack-name>` in `infra/cdk/` to preview changes
3. Deploy to dev and verify before merging

### Database Schema Changes

1. Create a new migration file in `infra/migrations/` following the naming convention: `NNN_description.sql`
2. Use `IF NOT EXISTS` and `ON CONFLICT` for idempotency where possible
3. Update `infra/migrations/README.md` with the new migration description
4. Test the migration against a local PostgreSQL instance

## Branch Strategy

- `main` — Production-ready code
- Feature branches — Branch from `main`, merge back via PR

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all tests pass locally
4. Open a PR with a clear description of what changed and why
5. Address review feedback
6. Merge after approval
