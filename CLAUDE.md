# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The Early Learning Standards (ELS) Platform: a serverless AWS pipeline that ingests US state early-learning-standards PDFs, uses Bedrock (Claude) + Textract to detect and normalize their hierarchy into a canonical schema, and stores the result in Aurora PostgreSQL. On top of it sit three web apps (Standards Explorer, Planning App, Landing Site). See [README.md](README.md) and [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) for the full picture — this file covers only what isn't obvious from those.

## Keep documentation in sync with substantial changes

When a change alters behavior, config, schema, or architecture (not a small bug fix), grep the docs (`README.md`, `CLAUDE.md`, `documentation/*.md`, and any other `.md` that describes the touched area) for stale references and update them in the same pass — don't leave the code change and the docs update as separate follow-up work. A doc describing removed/changed behavior is worse than no doc at all, since it reads as authoritative.

## Design direction for the detector & parser (READ BEFORE EDITING `detector.py` / `parser.py`)

**Goal: `detector.py` and `parser.py` should be LLM-driven, not rule-driven.** The intended architecture is "let the model reason about the document; keep the Python thin." Detection/parsing decisions — how to classify a level, how to build a code, how to handle age-band columns, how to strip a structural label — belong in the **prompt**, expressed as general document-structure principles, not in Python regexes and special-case branches.

**The problem we were fighting: overfitting to the golden set.** The golden states (CA, AZ, CO, TX) had each been made to pass by adding targeted, per-state Python logic that scored well on the goldens but **did not generalize**. The 2026-06 LLM-first migration (`tasking/detector_parser_llm_migration.md`, Tasks 1–8, completed 2026-06-27) removed that logic and moved each rule into the prompt as a general principle. The per-state helpers that are now **gone** — do not re-introduce them or anything shaped like them:

- `detector._LABEL_PREFIX_RE` + the label-strip half of `_strip_label_prefix`, and `parser._LABEL_CODE_RE` (`Strand N:` / `Concept N:`) → detector prompt rule 4: a `<Label> <id>: <Title>` heading's label-and-id IS the code, the text after the colon is the title (any structural-label word, not a fixed list).
- `parser._abbreviate_title` + `_CODE_ABBREV_LEN` → detector prompt rule 4: derive a ≤5-char uppercase code from the title (multi-word → initials e.g. `Concepts About Print`→`CAP`; single-word → first 4 letters e.g. `Vocabulary`→`VOCA`).
- `detector._TRAILING_DOMAIN_LABEL_RE` → detector prompt: a domain title's trailing structural noun (`Standard`, `Domain`) is not part of its name — emit the bare name.
- `parser._COLUMN_PREFIX_RE` / `_strip_column_prefix` + the PK-strip inside `_infer_domain_code` → parser prompt: a leading age/column token (e.g. `PK3.`) is excluded from the base hierarchical code.
- `parser._disambiguator_suffix`, `_derive_label_abbrev`, `_COLUMN_ABBREV_LEN` + the suffix re-application in `parse_llm_response` → parser prompt DISAMBIGUATE rule: side-by-side columns emit DISTINCT codes directly (age-range → month range `.36-48`; proficiency → first-4-uppercased `.DISC`). Only a thin numeric-counter uniqueness guard remains.
- the CA collision branch + `_PURE_NUMERIC_RE` in `abbreviate_element_codes` (and the now-empty `abbreviate_element_codes` / `normalize_code_to_canonical` shells) → parser prompt: a sub_strand and its child indicator must never share a code; the sub_strand derives its segment from its title with the same ≤5-char abbrev scheme.

A new per-state regex/branch in `detector.py` or `parser.py` is a regression in disguise even if it raises a golden score — flag it rather than adding it. The justified Python that survives is document-agnostic only: `generate_standard_id`, `normalize_parsed_codes`, `normalize_element_codes` (cross-chunk drift), `chunk_elements_by_domain` / `_split_oversized_chunk` / `chunk_text_blocks` / `_dedup_elements`, `_infer_domain_code` routing (PK strip removed), the generic age-band canonicalizers (`canonicalize_age_band`, `_normalize_age_band`, `_TRAILING_MARKER_RE`, terminal-period strip), and the JSON-extraction / schema-validation plumbing.

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
- Every detected element carries a `confidence` score but is never gated or dropped by it — all elements flow through to parsing and persistence, since every element is reviewed by a human downstream regardless of confidence.

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

# AWS Guidance

- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.