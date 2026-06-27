# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The Early Learning Standards (ELS) Platform: a serverless AWS pipeline that ingests US state early-learning-standards PDFs, uses Bedrock (Claude) + Textract to detect and normalize their hierarchy into a canonical schema, and stores the result in Aurora PostgreSQL. On top of it sit three web apps (Standards Explorer, Planning App, Landing Site). See [README.md](README.md) and [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) for the full picture — this file covers only what isn't obvious from those.

## Design direction for the detector & parser (READ BEFORE EDITING `detector.py` / `parser.py`)

**Goal: `detector.py` and `parser.py` should be LLM-driven, not rule-driven.** The intended architecture is "let the model reason about the document; keep the Python thin." Detection/parsing decisions — how to classify a level, how to build a code, how to handle age-band columns, how to strip a structural label — belong in the **prompt**, expressed as general document-structure principles, not in Python regexes and special-case branches.

**The problem we are actively fighting: overfitting to the golden set.** The current golden states (CA, AZ, CO, TX) were each made to pass by adding targeted Python logic — e.g. `_COLUMN_PREFIX_RE` (`PK\d+.` stripping), `_LABEL_PREFIX_RE` / `_strip_label_prefix` (`Strand N:` / `Concept N:` handling), `_derive_label_abbrev` / `_abbreviate_title` column abbreviations, the CA sub_strand/indicator code-collision branch in `abbreviate_element_codes`, `_TRAILING_DOMAIN_LABEL_RE`, and the `½`/`1/2` glyph folding. Each of these encodes a quirk of one document. They make the goldens score well but **do not generalize** — running a new state (e.g. Nevada, 2026-06-20) through the pipeline produces poor results because the new document's quirks aren't covered by these hardcoded rules.

**When working in these two files, prefer in this order:**
1. **Improve the prompt** so the LLM handles the case as a general principle. A rule that helps every document (e.g. "a structural label like `Strand 1:` is the code, not the title") belongs as a prompt instruction, stated generally — not as a Python regex keyed to specific label words.
2. **Only fall back to Python** for things that are genuinely deterministic post-processing and document-agnostic (JSON extraction, schema validation, ID derivation from already-clean fields, true cross-chunk reconciliation). New per-state regexes/branches are a smell — flag them rather than adding them.
3. **Never loosen the eval matchers or edit goldens to paper over a generalization gap.** Fix the golden DATA and canonicalize the model output instead (see the golden-consistency note below).

**Test for generalization, not just the goldens.** A change that raises a golden score but relies on a document-specific rule is a regression in disguise. Validate against a held-out state (Nevada is the current canary; PDFs in `standards/nevada_ses_standards_2025*.pdf`) before considering a detector/parser change done. The `evaluation-runner` skill auto-runs additional states for exactly this reason — use it.

## Two-language monorepo

The repo mixes two independently-managed toolchains. **Know which half you're in before running anything.**

- **Python** (`src/els_pipeline/`, `tests/`, `evaluation/`, `packages/agentcore-agent/`) — managed by `pyproject.toml`, run via `pytest` / `python -m`. Activate the venv first: `source venv/bin/activate` (a `.venv/` also exists; `venv/` is the one the README documents).
- **TypeScript** (`packages/*` except `agentcore-agent`, `infra/cdk/`) — pnpm workspace + Turborepo. Package names are `@els/*` (e.g. `@els/api`, `@els/shared`, `@els/frontend`). `@els/shared` holds the canonical TS types and is a dependency of every other JS package.

## Commands

```bash
# --- Python pipeline ---
source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v                              # all
pytest tests/property/ -v                     # property-based (Hypothesis)
pytest tests/integration/ -v                  # moto-mocked AWS
pytest tests/unit/ -v
pytest tests/unit/test_detector.py::TestX::test_y -v   # a single test
pytest tests/ --cov=els_pipeline --cov-report=html

# --- TS monorepo (from repo root; Turbo handles build ordering) ---
pnpm install
pnpm build | pnpm lint | pnpm test | pnpm typecheck
pnpm --filter @els/api test                   # one package; tests use vitest
pnpm --filter @els/api dev                     # watch/dev a single package
```

Single TS test: `cd packages/els-explorer-api && pnpm vitest --run path/to/file.test.ts`. Note `pnpm test` depends on `build` (see [turbo.json](turbo.json)), so a broken build blocks tests.

## Evaluation harness (`evaluation/`)

This is the actively-iterated quality-measurement layer for the detector and parser — separate from `tests/`. Two **decoupled** golden sets graded by two suites:

- `evaluation/eval_detector.py` grades the detector against `ground_truth_detector/{STATE}.json` (flat element list, run on `{STATE}-extraction.json`).
- `evaluation/eval_parser.py` grades the parser against `ground_truth_parser/{STATE}.json` (nested `NormalizedStandard` objects, run on `{STATE}-detection.json`).

They produce different shapes from different inputs and are annotated/iterated independently — don't assume a change to one affects the other.

```bash
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_detector --state CA --stability-runs 3   # LLM-determinism check
python -m evaluation.eval_parser --detection-dir outputs/05-31-26
```

`regression_cases` in each golden file map by `id` to a check function in `evaluation/regression_checks.py` — when adding a regression case, add the matching function or the suite logs `SKIP`. See [evaluation/README.md](evaluation/README.md) for annotation conventions.

## Pipeline architecture (the non-obvious parts)

- **All Lambda entry points live in one file**, `src/els_pipeline/handlers.py` (`ingestion_handler`, `extraction_handler`, `detection_handler`, `parsing_handler`, `validation_handler`, `persistence_handler`, plus the batch prepare/process/merge handlers). The corresponding logic lives in sibling modules (`detector.py`, `parser.py`, etc.); handlers are thin S3-in/S3-out wrappers.
- **Detection and parsing are batched** via a three-step prepare → Step-Functions-Map (max 3 concurrent) → merge pattern (`detection_batching.py`, `parse_batching.py`) to dodge Lambda timeouts on large docs. Detection batches by text-block chunks (`MAX_CHUNKS_PER_BATCH=5`); parsing batches by domain (`MAX_DOMAINS_PER_BATCH=3`) to keep related elements together.
- **Stages communicate through S3, not direct payloads.** Each run writes intermediate JSON under `{country}/{state}/{year}/intermediate/...` keyed by `run_id` — read these when debugging a stage in isolation.
- **Standard IDs are deterministic:** `{country}-{state}-{year}-{indicator_code}` (e.g. `US-CA-2021-LLD.1.2`). The `indicator_code` is fully qualified and carries any disambiguator (age prefix / column suffix) itself — there is no separate `domain_code` component (see `generate_standard_id` in `parser.py`). Pydantic `models.py` is the Python source of truth for the schema; `packages/shared/src/types.ts` mirrors it for TS — **keep these two in sync** when changing the data model.
- Elements below `CONFIDENCE_THRESHOLD` (0.8) are flagged for human review rather than dropped.

## Infrastructure & deploy

Four independent CDK stacks (`infra/cdk/lib/{pipeline,app,planning,landing-site}-stack.ts`), each with a deploy script in `scripts/`. CDK selects a stack via the `targetStack` context var (`bin/app.ts`). Docker must be running (CDK bundles Lambdas). The Explorer/Planning deploys need `DESCOPE_PROJECT_ID` set (Descope handles auth).

```bash
./scripts/deploy_els_pipeline.sh -e dev
DESCOPE_PROJECT_ID=<id> ./scripts/deploy_els_app.sh -e dev
DESCOPE_PROJECT_ID=<id> ./scripts/deploy_planning_app.sh -e dev
./scripts/deploy_landing_site.sh -e dev
```

DB schema evolves via numbered files in `infra/migrations/` (Aurora PostgreSQL). The Planning agent (`packages/agentcore-agent/`) is a Python Strands agent deployed to Bedrock AgentCore — **user identity is bound from the authenticated session, never chosen by the LLM**; preserve that when touching its tools.

## Config

Bedrock model IDs, bucket names, and batch sizes are all env vars — see [.env.example](.env.example). Defaults of note: detector uses Claude Opus, the detection depth-map pass uses Claude Haiku, and the parser uses Claude Sonnet.

## Claude Code skills

Two project skills live at `~/.claude/skills/` and are invoked automatically by Claude Code:

- **`download-pipeline-outputs`** (`~/.claude/skills/download-pipeline-outputs/SKILL.md`) — downloads detection, extraction, and parsing JSON from S3 for all four golden states (AZ, CA, CO, TX) into a date-stamped `outputs/MM-DD-YY/` folder. Invoke with e.g. "download pipeline outputs for run 15". Uses AWS profile `kinder-readiness-dev-cli`; run IDs are zero-padded to 3 digits. Output files are named `<STATE>-<type>.json` (e.g. `AZ-detection.json`).
- **`evaluation-runner`** (`~/.claude/skills/evaluation-runner/SKILL.md`) — runs the detector and parser eval suites against a local outputs folder and suggests fixes for low-scoring components.
