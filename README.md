# ELS Normalization Pipeline

A serverless pipeline that ingests early learning standards (ELS) documents from multiple countries and states, extracts their hierarchical structure using AI, and normalizes them into a consistent canonical format.

## What It Does

The pipeline takes PDF/HTML standards documents and runs them through a series of stages:

1. **Ingestion** — Uploads raw documents to S3 with country-based path structure
2. **Text Extraction** — Extracts text blocks from PDFs using AWS Textract
3. **Structure Detection** — Uses Bedrock (Claude) to identify hierarchy elements (domains, strands, indicators). Large documents are split into batches processed in parallel via Step Functions Map states.
4. **Hierarchy Parsing** — Normalizes detected elements into a consistent tree structure. Domain chunks are batched and processed in parallel, then merged.
5. **Validation** — Validates records against the canonical schema and enforces uniqueness
6. **Embedding Generation** — Generates vector embeddings via Bedrock Titan for similarity search
7. **Recommendation Generation** — Produces activity recommendations for parents and teachers
8. **Persistence** — Stores everything in Aurora PostgreSQL with pgvector

The whole thing is orchestrated by AWS Step Functions and deployed via CloudFormation.

## Architecture

```
S3 (raw PDFs) → Lambda: Ingester
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
             → Lambda: Embedding Generator (Bedrock Titan)
             → Lambda: Recommendation Generator (Bedrock Claude)
             → Lambda: Persister → Aurora PostgreSQL (pgvector)
```

The detection and parsing stages use an iterative batching pattern to avoid Lambda timeout issues on large documents. Each stage is split into three steps (prepare → parallel process → merge) orchestrated by Step Functions Map states.

**AWS Services used:** S3, Lambda, Step Functions, Textract, Bedrock, Aurora PostgreSQL Serverless v2, SNS, Secrets Manager, CloudWatch.

## S3 Path Structure

All paths are organized by country (ISO 3166-1 alpha-2):

```
Raw:       {country}/{state}/{year}/{filename}
Processed: {country}/{state}/{year}/{standard_id}.json
```

Example: `US/CA/2021/california_all_standards_2021.pdf` → `US/CA/2021/US-CA-2021-LLD-1.2.json`

## Project Layout

```
src/els_pipeline/     Core pipeline modules (ingester, extractor, detector, parser, validator,
                      detection_batching, parse_batching, etc.)
infra/                CloudFormation template and database migrations
scripts/              Deployment and manual testing scripts
tests/
  ├── property/       Property-based tests (Hypothesis)
  ├── integration/    Integration tests (moto-mocked AWS)
  └── unit/           Unit tests
standards/            Sample standards PDFs for testing
documentation/        Detailed guides (deployment, testing, AWS operations)
```

## Getting Started

### Prerequisites

- Python 3.13+
- AWS CLI v2 (configured with appropriate credentials)
- Access to AWS Bedrock models (Claude and Titan Embed)

### Local Setup

```bash
# Clone and install
git clone <repository-url>
cd els-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your values
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# By category
pytest tests/property/ -v       # Property-based (Hypothesis)
pytest tests/integration/ -v    # Integration (mocked AWS)
pytest tests/unit/ -v           # Unit

# With coverage
pytest tests/ --cov=els_pipeline --cov-report=html
```

### Deploying

```bash
# Deploy to dev (default)
./scripts/deploy.sh

# Deploy to a specific environment and region
./scripts/deploy.sh -e staging -r us-west-2
```

The deploy script packages Lambda functions, validates the CloudFormation template, deploys the stack, and outputs the resource names. Deployment takes ~10-15 minutes (Aurora cluster creation).

See [documentation/DEPLOYMENT.md](documentation/DEPLOYMENT.md) for full details.

## CI/CD

Pushes to `main` trigger the GitHub Actions workflow (`.github/workflows/deploy.yml`):

1. Runs all tests (unit, property, integration)
2. Deploys to dev
3. Deploys to prod (after dev succeeds)

## Configuration

Key environment variables (see `.env.example` for the full list):

| Variable                        | Description                               | Default                           |
| ------------------------------- | ----------------------------------------- | --------------------------------- |
| `ELS_RAW_BUCKET`                | S3 bucket for raw documents               | `els-raw-documents`               |
| `ELS_PROCESSED_BUCKET`          | S3 bucket for canonical JSON              | `els-processed-json`              |
| `BEDROCK_DETECTOR_LLM_MODEL_ID` | Bedrock model for structure detection     | `us.anthropic.claude-opus-4-6-v1` |
| `BEDROCK_PARSER_LLM_MODEL_ID`   | Bedrock model for parsing                 | `us.anthropic.claude-sonnet-4-6`  |
| `BEDROCK_EMBEDDING_MODEL_ID`    | Bedrock model for embeddings              | `amazon.titan-embed-text-v2:0`    |
| `CONFIDENCE_THRESHOLD`          | Min confidence before flagging for review | `0.7`                             |
| `MAX_CHUNKS_PER_BATCH`          | Max text-block chunks per detection batch | `5`                               |
| `MAX_DOMAINS_PER_BATCH`         | Max domain chunks per parse batch         | `3`                               |
| `DB_HOST`                       | Aurora PostgreSQL endpoint                | `localhost`                       |
| `DESCOPE_PROJECT_ID`            | Descope project ID for API authentication | —                                 |

## Documentation

- [Deployment Guide](documentation/DEPLOYMENT.md) — Infrastructure setup, GitHub secrets, manual and automated deployment
- [Testing Guide](documentation/COMPREHENSIVE_TESTING.md) — Testing strategy, running tests, coverage goals
- [AWS Operations Guide](documentation/AWS_TESTING.md) — Post-deployment verification, monitoring, troubleshooting, cost optimization
- [Infrastructure README](infra/README.md) — CloudFormation resources, S3 structure, IAM roles
- [Database Migrations](infra/migrations/README.md) — Schema evolution and migration instructions

## License

Internal use only.
