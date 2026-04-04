# Architecture Guide

## System Overview

The ELS Normalization Pipeline is a serverless system built on AWS that transforms unstructured early learning standards documents into a normalized, queryable dataset. It consists of:

1. A Python-based data pipeline orchestrated by Step Functions
2. A TypeScript REST API and React frontend for exploring the data (Standards Explorer)
3. An AI-powered planning application using Bedrock AgentCore (Planning App)
4. A project landing site

## Pipeline Stages

### 1. Ingestion

**Module:** `src/els_pipeline/ingester.py`
**Lambda handler:** `ingestion_handler`

Uploads raw PDF/HTML documents to S3 with metadata tags. Validates file format and constructs the S3 path using the country-based structure: `{country}/{state}/{year}/{filename}`.

Supported formats: `.pdf`, `.html`

### 2. Text Extraction

**Module:** `src/els_pipeline/extractor.py`
**Lambda handler:** `extraction_handler`

Extracts text blocks from PDFs using AWS Textract. Handles both synchronous (small documents) and asynchronous (large documents) Textract APIs. Sorts blocks by reading order and preserves table cell structure with row/column indices.

Output: List of `TextBlock` objects with text, page number, block type, confidence, and geometry.

### 3. Detection Batching

**Module:** `src/els_pipeline/detection_batching.py`
**Lambda handlers:** `detection_batch_preparer_handler`, `detection_batch_processor_handler`, `detection_merger_handler`

Large documents can have hundreds of text blocks. To avoid Lambda timeouts, detection is split into three steps:

1. **Prepare** — Splits text blocks into batches of `MAX_CHUNKS_PER_BATCH` (default: 5) and writes each batch to S3 with a manifest file
2. **Process** — Step Functions Map state invokes up to 3 concurrent Lambdas, each processing one batch through Bedrock Claude
3. **Merge** — Collects all batch results, deduplicates detected elements by code, and produces a single merged output

### 4. Structure Detection

**Module:** `src/els_pipeline/detector.py`
**Lambda handler:** `detection_handler`

Uses Bedrock Claude to identify hierarchical elements in text blocks. Each element is classified as a domain, strand, sub-strand, or indicator with a confidence score. Elements below the `CONFIDENCE_THRESHOLD` (default: 0.8) are flagged for human review.

The detection prompt instructs the LLM to extract structured JSON with fields: level, code, title, description, confidence, source_page, source_text.

### 5. Parse Batching

**Module:** `src/els_pipeline/parse_batching.py`
**Lambda handlers:** `parse_batch_preparer_handler`, `parse_batch_processor_handler`, `parse_merger_handler`

Same pattern as detection batching, but partitions by domain. Each batch contains up to `MAX_DOMAINS_PER_BATCH` (default: 3) domain groups. This ensures related elements stay together during parsing.

### 6. Hierarchy Parsing

**Module:** `src/els_pipeline/parser.py`
**Lambda handler:** `parsing_handler`

Normalizes detected elements into a consistent tree structure:

```
Document
  └── Domain (e.g., "Language and Literacy Development")
       └── Strand (e.g., "Reading")
            └── Sub-Strand (e.g., "Phonological Awareness")
                 └── Indicator (e.g., "Recognizes rhyming words")
```

Generates deterministic Standard IDs in the format: `{country}-{state}-{year}-{domain_code}-{indicator_code}` (e.g., `US-CA-2021-LLD-1.2`).

### 7. Validation

**Module:** `src/els_pipeline/validator.py`
**Lambda handler:** `validation_handler`

Validates each normalized record against the canonical schema using Pydantic models. Enforces:

- Required fields present and correctly typed
- Standard ID uniqueness
- Country code format (ISO 3166-1 alpha-2)
- Confidence scores in valid range

Valid records are serialized to canonical JSON and stored in the processed S3 bucket.

### 8. Embedding Generation

**Lambda handler:** `embedding_handler`

Generates vector embeddings for each indicator using Bedrock Titan Embed (`amazon.titan-embed-text-v2:0`). Embeddings enable similarity search across standards from different states.

### 9. Recommendation Generation

**Lambda handler:** `recommendation_handler`

Uses Bedrock Claude to generate activity recommendations for each indicator, targeted at two audiences: parents and teachers.

### 10. Persistence

**Module:** `src/els_pipeline/persister.py`

Stores all data in Aurora PostgreSQL Serverless v2 with the pgvector extension:

- Documents, domains, strands, sub-strands, indicators
- Vector embeddings (1024-dimensional)
- Recommendations
- Pipeline run metadata

## Data Models

Defined in `src/els_pipeline/models.py` and `packages/shared/src/types.ts`.

### Hierarchy

```
Document (country, state, year, title, source_url, age_band)
  └── Domain (code, name, description)
       └── Strand (code, name, description)
            └── Sub-Strand (code, name, description)
                 └── Indicator (standard_id, code, title, description, age_band, source_page)
```

### Key Enums

- **HierarchyLevel:** `domain`, `strand`, `sub_strand`, `indicator`
- **Audience:** `parent`, `teacher`
- **Status:** `success`, `error`, `completed`, `failed`, `partial`, `running`

### Standard ID Format

```
{country}-{state}-{year}-{domain_code}-{indicator_code}
```

Example: `US-CA-2021-LLD-1.2` = United States, California, 2021, Language and Literacy Development, Indicator 1.2

## S3 Path Structure

All paths are organized by country (ISO 3166-1 alpha-2):

| Bucket         | Pattern                                                  | Example                                         |
| -------------- | -------------------------------------------------------- | ----------------------------------------------- |
| Raw documents  | `{country}/{state}/{year}/{filename}`                    | `US/CA/2021/california_standards.pdf`           |
| Processed JSON | `{country}/{state}/{year}/{standard_id}.json`            | `US/CA/2021/US-CA-2021-LLD-1.2.json`            |
| Embeddings     | `{country}/{state}/{year}/embeddings/{standard_id}.json` | `US/CA/2021/embeddings/US-CA-2021-LLD-1.2.json` |

### Intermediate Data

Each pipeline run writes intermediate output for debugging:

```
{country}/{state}/{year}/intermediate/
  ├── extraction/{run_id}.json
  ├── detection/manifest/{run_id}.json
  ├── detection/batch-N/{run_id}.json
  ├── detection/result-N/{run_id}.json
  ├── detection/{run_id}.json
  ├── parsing/manifest/{run_id}.json
  ├── parsing/batch-N/{run_id}.json
  ├── parsing/result-N/{run_id}.json
  ├── parsing/{run_id}.json
  └── validation/{run_id}.json
```

## Web Applications

### Standards Explorer

- **API** (`packages/els-explorer-api/`): Hono REST API running on Lambda behind API Gateway. Provides CRUD endpoints for documents, domains, strands, sub-strands, and indicators. Supports filtering by country/state, human verification workflow, and soft deletes.
- **Frontend** (`packages/els-explorer-frontend/`): React 19 SPA with Tailwind CSS. Browse the standards hierarchy, edit elements, mark as verified. Authenticated via Descope.

### Planning App

- **API** (`packages/planning-api/`): Hono API that proxies WebSocket connections to Bedrock AgentCore. Handles Descope authentication and forwards user tokens.
- **Agent** (`packages/agentcore-agent/`): Python Strands agent deployed to Bedrock AgentCore Runtime. Has tools for querying standards data and managing learning plans (CRUD). User identity is bound from the authenticated session — the LLM never controls which user's data is accessed.
- **Frontend** (`packages/planning-frontend/`): React chat UI using `@chatscope/chat-ui-kit-react`. Supports real-time streaming, plan creation/editing, and PDF export.

### Landing Site

- **Frontend** (`packages/landing-site/`): Static React landing page deployed to S3 + CloudFront.

## AWS Services

| Service                         | Purpose                                                     |
| ------------------------------- | ----------------------------------------------------------- |
| S3                              | Document storage (raw, processed, embeddings, intermediate) |
| Lambda                          | Pipeline stage execution, API handlers                      |
| Step Functions                  | Pipeline orchestration, parallel batch processing           |
| Textract                        | PDF text extraction                                         |
| Bedrock                         | LLM inference (Claude) and embeddings (Titan)               |
| Aurora PostgreSQL Serverless v2 | Persistent storage with pgvector                            |
| API Gateway                     | REST API endpoints                                          |
| CloudFront                      | Frontend CDN                                                |
| Secrets Manager                 | Database credentials                                        |
| SNS                             | Pipeline notifications                                      |
| CloudWatch                      | Logging and monitoring                                      |
| Bedrock AgentCore               | Managed agent runtime for planning                          |
| Route53                         | Custom domain DNS                                           |
| ACM                             | SSL certificates                                            |

## Infrastructure as Code

All infrastructure is defined in AWS CDK (TypeScript) under `infra/cdk/`:

| Stack    | File                        | Description                               |
| -------- | --------------------------- | ----------------------------------------- |
| Pipeline | `lib/pipeline-stack.ts`     | S3, Lambda, Step Functions, Aurora, IAM   |
| App      | `lib/app-stack.ts`          | Explorer API, frontend hosting            |
| Planning | `lib/planning-stack.ts`     | Planning API, AgentCore, frontend hosting |
| Landing  | `lib/landing-site-stack.ts` | Landing site hosting                      |

The CDK app entry point (`bin/app.ts`) supports selective stack deployment via the `targetStack` context variable.

## Database Schema

PostgreSQL with pgvector. Migrations are in `infra/migrations/`:

| Migration | Description                                                                                                      |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| 001       | Initial schema: documents, domains, strands, sub_strands, indicators, embeddings, recommendations, pipeline_runs |
| 002       | Add description columns to domains/strands/sub_strands, age_band to indicators                                   |
| 003       | Add title column to indicators                                                                                   |
| 004       | Alter age_band column type                                                                                       |
| 005       | Add verification columns (human_verified, verified_at, verified_by, edited_at, edited_by)                        |
| 006       | Add s3_key column to documents                                                                                   |
| 007       | Add soft delete columns (deleted, deleted_at, deleted_by)                                                        |
| 008       | Add planning tables (plans)                                                                                      |
| 009       | Alter indicator description to required                                                                          |

## Monorepo Structure

The project uses a pnpm workspace with Turborepo for the Node.js packages:

- `pnpm-workspace.yaml` defines `packages/*` as workspace members
- `turbo.json` defines build/dev/lint/test/typecheck tasks with dependency ordering
- `@els/shared` is a dependency of all API and frontend packages
- Python code (`src/`, `tests/`) is managed separately via `pyproject.toml`
