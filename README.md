# Early Learning Standards (ELS) Platform

A serverless pipeline that ingests early learning standards (ELS) documents from multiple US states, extracts their hierarchical structure using AI, and normalizes them into a consistent canonical format — plus web apps for exploring and building learning plans from the resulting data.

## What It Does

Early learning standards vary wildly across states — different formats, structures, and terminology. This pipeline takes raw PDF documents and produces a unified, queryable dataset:

1. **Ingestion** — Uploads raw documents to S3 with country-based path structure
2. **Text Extraction** — Extracts text blocks from PDFs using AWS Textract
3. **Structure Detection** — Uses Bedrock (Claude) to identify hierarchy elements (domains, strands, indicators), with large documents batched and processed in parallel via Step Functions Map states
4. **Hierarchy Parsing** — Normalizes detected elements into a consistent tree structure, also batched in parallel
5. **Validation** — Validates records against the canonical schema and enforces uniqueness
6. **Persistence** — Stores everything in Aurora PostgreSQL

On top of the pipeline, there are three web applications:

- **Standards Explorer** — Browse, search, edit, and verify the normalized standards hierarchy
- **Planning App** — AI-powered chat interface for generating personalized learning plans using Bedrock AgentCore
- **Landing Site** — Project landing page

The whole thing is orchestrated by AWS Step Functions and deployed via AWS CDK.

## Architecture

```
PDF → Lambda: Ingester
    → Lambda: Text Extractor (Textract)
    → Detection Batching:
        Lambda: Prepare Detection Batches
        → Step Functions Map: Detect Batch (parallel, max 3)
        → Lambda: Merge Detection Results
    → Parse Batching:
        Lambda: Prepare Parse Batches
        → Step Functions Map: Parse Batch (parallel, max 3)
        → Lambda: Merge Parse Results
    → Lambda: Validator → S3 (canonical JSON)
    → Lambda: Persister → Aurora PostgreSQL
```

The detection and parsing stages use an iterative batching pattern to avoid Lambda timeout issues on large documents. Each stage splits into three steps (prepare → parallel process → merge) orchestrated by Step Functions Map states.

## Project Layout

```
src/els_pipeline/          Python pipeline modules (ingester, extractor, detector,
                           parser, validator, batching, embeddings, etc.)
packages/
  ├── shared/              Shared TypeScript types used by all web packages
  ├── els-explorer-api/    Hono REST API for the standards explorer
  ├── els-explorer-frontend/ React frontend for browsing/editing standards
  ├── planning-api/        Hono API proxying to Bedrock AgentCore for planning
  ├── planning-frontend/   React chat UI for AI-powered learning plans
  ├── agentcore-agent/     Python Strands agent deployed to Bedrock AgentCore
  └── landing-site/        Project landing page (React)
infra/
  ├── cdk/                 AWS CDK stacks (pipeline, app, planning, landing)
  └── migrations/          PostgreSQL migration scripts
scripts/                   Deployment scripts and manual testing tools
tests/
  ├── property/            Property-based tests (Hypothesis)
  ├── integration/         Integration tests (moto-mocked AWS)
  └── unit/                Unit tests
standards/                 Sample standards PDFs for testing
documentation/             Detailed guides
```

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 20+ and pnpm 9+
- AWS CLI v2 (configured with appropriate credentials)
- Docker (required by CDK for Lambda bundling)
- Access to AWS Bedrock models (Claude and Titan Embed)

### Local Setup

```bash
# Clone and install Python dependencies
git clone <repository-url>
cd els-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Install Node.js dependencies
pnpm install

# Copy and configure environment
cp .env.example .env
# Edit .env with your values
```

### Running Tests

```bash
# Python pipeline tests (all)
pytest tests/ -v

# By category
pytest tests/property/ -v       # Property-based (Hypothesis)
pytest tests/integration/ -v    # Integration (mocked AWS)
pytest tests/unit/ -v           # Unit

# With coverage
pytest tests/ --cov=els_pipeline --cov-report=html

# Node.js package tests
pnpm test
```

### Deploying

There are four independent CDK stacks, each with its own deploy script:

```bash
# Pipeline infrastructure (S3, Lambda, Step Functions, Aurora, etc.)
./scripts/deploy_els_pipeline.sh -e dev

# Standards Explorer app (API + frontend)
DESCOPE_PROJECT_ID=<your-id> ./scripts/deploy_els_app.sh -e dev

# Planning app (API + AgentCore + frontend)
DESCOPE_PROJECT_ID=<your-id> ./scripts/deploy_planning_app.sh -e dev

# Landing site
./scripts/deploy_landing_site.sh -e dev
```

See [documentation/DEPLOYMENT.md](documentation/DEPLOYMENT.md) for full details.

## Configuration

Key environment variables (see `.env.example` for the full list):

| Variable                        | Description                               | Default                          |
| ------------------------------- | ----------------------------------------- | -------------------------------- |
| `ELS_RAW_BUCKET`                | S3 bucket for raw documents               | `els-raw-documents`              |
| `ELS_PROCESSED_BUCKET`          | S3 bucket for canonical JSON              | `els-processed-json`             |
| `BEDROCK_DETECTOR_LLM_MODEL_ID` | Bedrock model for structure detection     | `us.anthropic.claude-opus-4-7`   |
| `BEDROCK_PARSER_LLM_MODEL_ID`   | Bedrock model for parsing                 | `us.anthropic.claude-sonnet-4-6` |
| `BEDROCK_EMBEDDING_MODEL_ID`    | Bedrock model for embeddings              | `amazon.titan-embed-text-v2:0`   |
| `CONFIDENCE_THRESHOLD`          | Min confidence before flagging for review | `0.8`                            |
| `MAX_CHUNKS_PER_BATCH`          | Max text-block chunks per detection batch | `5`                              |
| `MAX_DOMAINS_PER_BATCH`         | Max domain chunks per parse batch         | `3`                              |
| `DB_HOST`                       | Aurora PostgreSQL endpoint                | `localhost`                      |
| `DESCOPE_PROJECT_ID`            | Descope project ID for API authentication | —                                |

## Documentation

- [Deployment Guide](documentation/DEPLOYMENT.md) — All four stacks, prerequisites, scripts, and options
- [Testing Guide](documentation/TESTING.md) — Testing strategy, running tests, coverage goals
- [Architecture Guide](documentation/ARCHITECTURE.md) — Pipeline stages, data flow, batching pattern, data models
- [API Reference](documentation/API.md) — Explorer and Planning API endpoints
- [AWS Operations Guide](documentation/AWS_OPERATIONS.md) — Post-deployment verification, monitoring, troubleshooting, cost
- [Infrastructure Guide](infra/README.md) — CDK stacks, S3 structure, IAM roles
- [Database Migrations](infra/migrations/README.md) — Schema evolution and migration instructions
- [Contributing Guide](documentation/CONTRIBUTING.md) — Development workflow, code style, PR process

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
