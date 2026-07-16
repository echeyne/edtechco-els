# Testing Guide

## Strategy

The project uses a multi-tier testing approach:

### Python Pipeline Tests

| Tier           | Framework      | Purpose                                                       | AWS Required |
| -------------- | -------------- | ------------------------------------------------------------- | ------------ |
| Property-based | Hypothesis     | Verify universal correctness properties with generated inputs | No           |
| Integration    | pytest + moto  | Test components with mocked AWS services                      | No           |
| Unit           | pytest         | Test utility functions and helpers                            | No           |
| Manual         | Python scripts | Verify against real deployed infrastructure                   | Yes          |

### Node.js Package Tests

| Package                  | Framework                | Purpose                                            |
| ------------------------ | ------------------------ | -------------------------------------------------- |
| `@els/api`               | vitest                   | API route handlers, database queries               |
| `@els/frontend`          | vitest + Testing Library | React component rendering and interaction          |
| `@els/planning-api`      | vitest                   | Planning API routes, auth middleware, plan queries |
| `@els/planning-frontend` | vitest + Testing Library | Chat UI components                                 |
| `@els/landing-site`      | vitest (configured)      | **No test files yet** — `pnpm test` is a no-op     |
| `@els/shared`            | —                        | Types only; no test script                         |

Property-based testing is not Python-only: both API packages use `fast-check` for invariants that unit tests miss — `verifyRoundTrip`, `editAudit`, `cascadeDelete`, and `filters` in `@els/api`, and `plans.property` / `plans.referential-integrity` in `@els/planning-api`.

## Running Tests

### Python Pipeline

```bash
# Install dev dependencies
pip install -e ".[dev]"

# All tests
pytest tests/ -v

# By category
pytest tests/property/ -v
pytest tests/integration/ -v
pytest tests/unit/ -v

# With coverage
pytest tests/ --cov=els_pipeline --cov-report=html
open htmlcov/index.html

# Specific component
pytest tests/property/test_ingestion_props.py -v
pytest tests/integration/test_ingester_integration.py -v

# Batching tests
pytest tests/property/test_detection_batching_props.py -v
pytest tests/property/test_parse_batching_props.py -v
pytest tests/integration/test_detection_batching.py -v
pytest tests/integration/test_detect_batch.py -v
pytest tests/integration/test_merge_detection_results.py -v
pytest tests/integration/test_parse_batching.py -v
pytest tests/integration/test_merge_parse_results.py -v
```

### Node.js Packages

```bash
# All packages (via Turborepo)
pnpm test

# Specific package
pnpm --filter @els/api test
pnpm --filter @els/frontend test
pnpm --filter @els/planning-api test
pnpm --filter @els/planning-frontend test
```

### Manual AWS Tests (requires deployment)

These scripts test against real deployed infrastructure:

```bash
python scripts/test_ingester_manual.py
python scripts/test_extractor_manual.py
python scripts/test_detector_manual.py
python scripts/test_parser_manual.py
python scripts/test_validator_manual.py
python scripts/test_db_manual.py
python scripts/test_pipeline_manual.py
```

Requires environment variables set (see [Environment Setup](#environment-setup-for-aws-tests) below).

## Component Coverage

| Component      | Property Tests                                                                                            | Integration Tests   | Manual Test        |
| -------------- | --------------------------------------------------------------------------------------------------------- | ------------------- | ------------------ |
| Ingester       | S3 path construction, metadata completeness, format validation                                            | Mocked S3           | Real S3 upload     |
| Extractor      | Block reading order, table cell structure, page numbers                                                   | Mocked Textract     | Real Textract      |
| Detector       | Confidence threshold flagging                                                                             | Mocked Bedrock      | Real Bedrock LLM   |
| Det. Batching  | Batch no-data-loss, batch size constraint, dedup correctness, status determination, review count accuracy | Mocked S3 + Bedrock | Step Functions Map |
| Parser         | Level normalization, hierarchy mapping, Standard_ID determinism, orphan detection                         | Logic testing       | Sample data        |
| Parse Batching | Exact partitioning, batch size constraint, review element filtering, merge completeness                   | Mocked S3 + Bedrock | Step Functions Map |
| Validator      | Schema validation, error reporting, uniqueness, serialization round-trip                                  | Mocked S3           | Real S3 storage    |
| Database       | Query filter correctness                                                                                  | Test DB             | Real Aurora        |
| Orchestrator   | Stage result completeness, run count invariants                                                           | Mocked stages       | Step Functions     |

Unit tests (`tests/unit/`) cover the narrower deterministic helpers that the tiers above don't reach: `test_extractor_repair.py` (the PyMuPDF spacing repair), `test_parser_chunking.py`, `test_parser_domain_anchor.py`, `test_s3_helpers.py`, and `test_db.py`.

## Property-Based Testing

Property tests use [Hypothesis](https://hypothesis.readthedocs.io/) to generate random inputs and verify that correctness properties always hold. Configuration in `pyproject.toml`:

```toml
[tool.hypothesis]
max_examples = 10
deadline = 1000
```

Examples of properties tested:

- Ingester S3 paths never contain double slashes or leading slashes
- Detection batching preserves all text blocks (no data loss)
- Batch sizes never exceed `MAX_CHUNKS_PER_BATCH`
- Deduplication keeps the highest-confidence element for each code
- Standard IDs are deterministic given the same inputs
- Validation rejects records with missing required fields
- Parse batching partitions elements exactly by domain

To run with more examples for thorough testing:

```bash
pytest tests/property/ -v --hypothesis-max-examples=100
```

## Evaluation vs. Tests

`tests/` and `evaluation/` answer different questions, and a green test suite does **not** mean the pipeline reads documents well.

- **`tests/`** — is the code correct? Deterministic, no real LLM calls, runs in CI-time.
- **`evaluation/`** — how well does the LLM actually read real state documents? Calls Bedrock, graded against hand-annotated golden sets, scores drift as prompts change.

Any change to `detector.py` or `parser.py` (or their prompts) should be graded by the eval suites, not just by `pytest`:

```bash
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_parser --detection-dir outputs/MM-DD-YY

# LLM-determinism check: re-run N times, report disagreement rate
python -m evaluation.eval_detector --state CA --stability-runs 3
```

Because the LLM stages are prompt-driven, the failure mode to watch for is **overfitting to the goldens** — a change that lifts AZ/CA/CO/TX by encoding a document-specific rule. Validate against a held-out state (Nevada is the current canary) before calling a detector/parser change done. See [evaluation/README.md](../evaluation/README.md) and the design-direction section of [CLAUDE.md](../CLAUDE.md).

## Coverage Goals

- Overall: > 80%
- Critical paths (ingestion, validation, batching, persistence): > 90%
- All correctness properties covered by property tests
- All AWS service interactions covered by integration tests

## Environment Setup for AWS Tests

```bash
# S3 buckets (from stack outputs)
export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
export ELS_PROCESSED_BUCKET="els-processed-json-dev-<account-id>"
export AWS_REGION="us-east-1"

# Database (from Secrets Manager)
export DB_HOST="<aurora-endpoint>"
export DB_PORT="5432"
export DB_NAME="els_corpus"
export DB_USER="postgres"
export DB_PASSWORD="<from-secrets-manager>"

# Bedrock models
export BEDROCK_DETECTOR_LLM_MODEL_ID=us.anthropic.claude-opus-4-6-v1
export BEDROCK_DEPTH_MAP_LLM_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
export BEDROCK_PARSER_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-6

# Pipeline config
export MAX_CHUNKS_PER_BATCH=5
export MAX_DOMAINS_PER_BATCH=3
```

Or copy `.env.example` to `.env` and fill in values.

## Debugging

```bash
# Verbose output
pytest tests/ -vv

# Stop on first failure
pytest tests/ -x

# Drop into debugger on failure
pytest tests/ --pdb

# Show print statements
pytest tests/ -s

# Run a single test
pytest tests/integration/test_ingester_integration.py::test_ingester_with_mocked_s3_success -v
```

## Troubleshooting

| Issue                               | Fix                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `ModuleNotFoundError: els_pipeline` | Run `pip install -e .` from project root                                 |
| `NoSuchBucket`                      | Check `ELS_RAW_BUCKET` env var and CloudFormation outputs                |
| `AccessDenied`                      | Verify credentials: `aws sts get-caller-identity`                        |
| Property tests timeout              | `pytest tests/property/ --hypothesis-max-examples=10`                    |
| moto not installed                  | `pip install 'moto[s3,textract,bedrock]'`                                |
| vitest not found                    | Run `pnpm install` from project root                                     |
| TypeScript build errors             | Run `pnpm --filter @els/shared build` first (shared types must be built) |
