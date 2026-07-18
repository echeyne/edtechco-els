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

Extraction is **hybrid**: Textract provides the layout (block types, geometry, table structure), but its OCR can fuse adjacent words together ("thechild" instead of "the child"). To repair this, the extractor also opens the PDF with PyMuPDF (`fitz`) and uses the PDF's own embedded text layer as a spacing oracle — `_repair_block_spacing` matches each Textract line against the de-spaced page text and restores the correct word boundaries.

Matching details that matter: the comparison runs over a **folded** view of both sides, because a PDF text layer renders punctuation typographically (`Children’s`) where Textract OCRs ASCII (`Children's`) — without folding, most lines fail to match at all. The fold is strictly 1-to-1 (curly quotes, dashes) so offsets stay aligned; length-changing normalization such as NFKC is deliberately avoided. Zero-width and soft-hyphen characters are dropped from the index rather than treated as whitespace, so a hyphenated line wrap rejoins into one word. The repaired string is rebuilt from the **block's own characters**, with the text layer contributing only the gap positions, so only whitespace ever changes — never a character. Any whitespace run, including a line-wrap newline, becomes exactly one space. A line whose folded form appears more than once on the page is left untouched rather than guessed at.

If the PDF has no usable text layer (a pure scan), the Textract text is used as-is. PyMuPDF must be present in the Lambda bundle (see `infra/cdk/lib/constructs/pipeline-lambda.ts`) — if it is missing the repair no-ops silently in the output, so its absence is logged at ERROR.

Output: List of `TextBlock` objects with text, page number, block type, confidence, and geometry.

### 3. Detection Batching

**Module:** `src/els_pipeline/detection_batching.py`
**Lambda handlers:** `prepare_detection_batches_handler`, `detect_batch_handler`, `merge_detection_results_handler`

Large documents can have hundreds of text blocks. To avoid Lambda timeouts, detection is split into three steps:

1. **Prepare** — Splits text blocks into batches of `MAX_CHUNKS_PER_BATCH` (default: 5) and writes each batch to S3 with a manifest file
2. **Process** — Step Functions Map state invokes up to 3 concurrent Lambdas, each processing one batch through Bedrock Claude
3. **Merge** — Collects all batch results and de-duplicates them by delegating to `detector._dedup_elements`, the same function the non-batched path uses, so the two paths cannot drift (they have before). If a batch element fails model validation the merge falls back to a conservative key-based de-dup.

### 4. Structure Detection

**Module:** `src/els_pipeline/detector.py`
**Lambda handler:** `detection_handler`

Uses Bedrock Claude to identify hierarchical elements in text blocks. Detection runs as **two passes** (`detect_structure`):

1. **Pass 1 — depth-map inference** (`infer_depth_map`): a sample of blocks taken evenly across the document is sent to a lightweight model (`BEDROCK_DEPTH_MAP_LLM_MODEL_ID`, default Claude Haiku) to infer the document's nesting hierarchy (`doc_depths`). This runs once per document. If it fails, detection falls back to a no-depth-map mode.
2. **Pass 2 — per-chunk extraction**: blocks are chunked with token overlap (`chunk_text_blocks`) and each chunk is sent to the detector model (`BEDROCK_DETECTOR_LLM_MODEL_ID`, default Claude Opus) along with the depth map, so the model classifies elements by document depth rather than re-guessing per chunk. Elements re-emitted at overlapping chunk boundaries are collapsed by `_dedup_elements`.

Each element is classified as a domain, strand, sub-strand, or indicator with a confidence score. The score is kept on `DetectedElement` as metadata only — there is no confidence gate; every element flows through to parsing and persistence, since every element gets reviewed by a human downstream regardless of confidence.

The detection prompt instructs the LLM to extract structured JSON with fields: level, code, title, description, confidence, source_page, source_text, and age_band (populated for indicators that come from age-banded columns, e.g. "Early (3 to 4 ½ Years)", "PK3").

#### Column tagging in the prompt

Textract records a normalized bounding box for every block, but a page-only serialization (`[Page 12] …`) throws that away — and on a multi-column page the blocks arrive interleaved line by line, so the model has no way to tell which column a line came from and crosses their contents. `_serialize_blocks_for_prompt` therefore tags each prompt line with the column it was laid out in: `[Page 12 | col 2] …`.

`_assign_column_indices` derives the columns from each page's own distribution of left edges — no absolute coordinates. It collapses jitter-identical left edges into candidate edges, keeps only the populous ones (a real column runs the height of the page; a spanning header or an indented sub-list does not, so it cannot bridge two columns), merges edges closer together than the page's median block width, and assigns every block to its nearest surviving edge. Pages that resolve to a single column, or whose geometry is missing or degenerate, emit the plain `[Page N]` tag.

Blocks stay in **document order** rather than being re-sorted into column order: `chunk_text_blocks` slices this same sequence into overlapping chunks, so re-ordering would separate a column's head from its tail, and row adjacency is what ties the columns of one age-band row together. The tag carries the signal without moving anything.

#### Overlap de-duplication

`_dedup_elements` handles the two shapes a chunk boundary produces. An element may be emitted **whole twice** under drifting codes (one domain arriving as both `SED` and `I`), or **once truncated and once complete** — chunk N ran out of text mid-sentence while chunk N+1 saw the element whole. Codes are reconciled first, by the same `parser.normalize_element_codes` machinery the parser uses, which collapses the first shape; the second is collapsed by prefix dominance, keeping the longer title and the richer description.

Both passes are scoped by the element's owning domain (`parser.assign_domain_scopes`), because two domains can legitimately hold same-titled children — CA's ELD and FLD domains each own a "Listening and Speaking" strand and a "Vocabulary" sub-strand. Prefix dominance additionally requires a matching level, age band and code, and a substantial word-boundary prefix, so that genuinely distinct siblings ("Physical Development" vs "Physical Development and Health") are never merged.

#### Design constraint: the detector and parser are LLM-driven, not rule-driven

Detection and parsing decisions — how to classify a level, how to build a code, how to handle age-band columns, how to strip a structural label — live in the **prompt** as general document-structure principles, not in Python regexes or per-state branches. The June 2026 LLM-first migration removed the per-state helpers that had accumulated to make the golden states pass; a new state-specific regex in `detector.py` or `parser.py` is treated as a regression even if it raises a golden score. The Python that remains is document-agnostic only: JSON extraction, schema validation, ID derivation, cross-chunk reconciliation, and chunking.

See the design-direction section of [CLAUDE.md](../CLAUDE.md) for the full rules and the list of helpers that were deliberately removed.

### 5. Parse Batching

**Module:** `src/els_pipeline/parse_batching.py`
**Lambda handlers:** `prepare_parse_batches_handler`, `parse_batch_handler`, `merge_parse_results_handler`

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

Generates deterministic Standard IDs in the format `{country}-{state}-{year}-{indicator_code}` (e.g., `US-CA-2021-LLD.1.2`) — see [Standard ID Format](#standard-id-format) below.

### 7. Validation

**Module:** `src/els_pipeline/validator.py`
**Lambda handler:** `validation_handler`

Validates each normalized record against the canonical schema using Pydantic models. Enforces:

- Required fields present and correctly typed
- Standard ID uniqueness
- Country code format (ISO 3166-1 alpha-2)
- Confidence scores in valid range

Valid records are serialized to canonical JSON and stored in the processed S3 bucket.

### 8. Persistence

**Module:** `src/els_pipeline/persister.py`

Stores all data in Aurora PostgreSQL Serverless v2:

- Documents, domains, strands, sub-strands, indicators
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
- **Status:** `success`, `error`, `completed`, `failed`, `partial`, `running`

### Standard ID Format

```
{COUNTRY}-{STATE}-{YEAR}-{INDICATOR_CODE}
```

Example: `US-CA-2021-LLD.1.2` = United States, California, 2021, indicator `LLD.1.2`.

There is **no separate `domain_code` component**. The `indicator_code` is already fully qualified — it carries the domain segment and any disambiguator it needs, so `generate_standard_id` (in `parser.py`) is a single clean rule rather than a stack of special cases. Disambiguators come in two shapes:

| Shape           | Where it goes | Example                                                  |
| --------------- | ------------- | -------------------------------------------------------- |
| Age prefix      | Leading       | TX `PK3.I.A.2` vs `PK4.I.A.2`                            |
| Column suffix   | Trailing      | CA `ELD.1.0.VOC.1.1.DISC` vs `ELD.1.0.VOC.1.1.BRD`       |

This is what keeps side-by-side age/proficiency columns from collapsing into a single ID.

## S3 Path Structure

All paths are organized by country (ISO 3166-1 alpha-2):

| Bucket         | Pattern                                       | Example                               |
| -------------- | --------------------------------------------- | ------------------------------------- |
| Raw documents  | `{country}/{state}/{year}/{filename}`         | `US/CA/2021/california_standards.pdf` |
| Processed JSON | `{country}/{state}/{year}/{standard_id}.json` | `US/CA/2021/US-CA-2021-LLD.1.2.json`  |

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

## Quality Measurement (Evaluation Harness)

`evaluation/` is a standing quality layer for the detector and parser, separate from `tests/`. Where `tests/` asserts that the code is correct, `evaluation/` measures how well the LLM stages actually read real documents — it is the thing you iterate against when changing a prompt.

Two **decoupled** golden sets, graded by two suites:

| Suite                        | Golden set                | Input                     | Compares                                        |
| ---------------------------- | ------------------------- | ------------------------- | ----------------------------------------------- |
| `evaluation/eval_detector.py` | `ground_truth_detector/`  | `{STATE}-extraction.json` | Flat list of detected elements                  |
| `evaluation/eval_parser.py`   | `ground_truth_parser/`    | `{STATE}-detection.json`  | Nested `NormalizedStandard` objects, field-wise |

They produce different shapes from different inputs and are annotated independently — a change to one does not imply a change to the other. Golden states are AZ, CA, CO, and TX; **Nevada is the held-out canary** used to check that a change generalizes rather than overfitting the goldens.

See [evaluation/README.md](../evaluation/README.md) for annotation conventions and how to run each suite.

## Web Applications

### Standards Explorer

- **API** (`packages/els-explorer-api/`): Hono REST API running on Lambda behind API Gateway. Provides CRUD endpoints for documents, domains, strands, sub-strands, and indicators. Supports filtering by country/state, human verification workflow, and soft deletes.
- **Frontend** (`packages/els-explorer-frontend/`): React 19 SPA with Tailwind CSS. Browse the standards hierarchy, edit elements, mark as verified. Authenticated via Descope.

### Planning App

- **API** (`packages/planning-api/`): Hono API that authenticates the user via Descope, then returns a short-lived presigned `wss://` URL for the Bedrock AgentCore runtime (`/chat` route). The browser connects to AgentCore directly over that WebSocket — the API does not proxy the stream. The user's Descope JWT (and optional plan ID) are embedded as `X-Amzn-Bedrock-AgentCore-Runtime-Custom-*` query params so identity is bound server-side. A `/plans` route provides plan **reads and deletes only** — plans are created and updated by the agent's tools during a chat session, not by the frontend posting a plan body.
- **Agent** (`packages/agentcore-agent/`): Python Strands agent deployed to Bedrock AgentCore Runtime. Has tools for querying standards data and managing learning plans (CRUD). User identity is bound from the authenticated session — the LLM never controls which user's data is accessed.
- **Frontend** (`packages/planning-frontend/`): React chat UI using `@chatscope/chat-ui-kit-react`. Supports real-time streaming, plan creation/editing, and PDF export.

### Landing Site

- **Frontend** (`packages/landing-site/`): Static React landing page deployed to S3 + CloudFront.

## AWS Services

| Service                         | Purpose                                                     |
| ------------------------------- | ----------------------------------------------------------- |
| S3                              | Document storage (raw, processed, intermediate)             |
| Lambda                          | Pipeline stage execution, API handlers                      |
| Step Functions                  | Pipeline orchestration, parallel batch processing           |
| Textract                        | PDF text extraction                                         |
| Bedrock                         | LLM inference (Claude)                                      |
| Aurora PostgreSQL Serverless v2 | Persistent storage                                          |
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

The CDK app entry point (`bin/app.ts`) supports selective stack deployment via the `targetStack` context variable. Reusable constructs shared across stacks live in `lib/constructs/` (`pipeline-lambda.ts`, `pipeline-dashboard.ts`, `frontend-distribution.ts`).

## Database Schema

PostgreSQL. Migrations are in `infra/migrations/`:

| Migration | Description                                                                                                      |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| 001       | Initial schema: documents, domains, strands, sub_strands, indicators, embeddings, recommendations, pipeline_runs (embeddings/recommendations later dropped in 011) |
| 002       | Add description columns to domains/strands/sub_strands, age_band to indicators                                   |
| 003       | Add title column to indicators                                                                                   |
| 004       | Alter age_band column type                                                                                       |
| 005       | Add verification columns (human_verified, verified_at, verified_by, edited_at, edited_by)                        |
| 006       | Add s3_key column to documents                                                                                   |
| 007       | Add soft delete columns (deleted, deleted_at, deleted_by)                                                        |
| 008       | Add planning tables (plans)                                                                                      |
| 009       | Alter indicator description to required                                                                          |
| 010       | Add nullable `order` column to domains for user-defined ordering (falls back to `ORDER BY code`)                |
| 011       | Drop unused embeddings/recommendations tables and pipeline_runs.total_embedded/total_recommendations columns     |

## Monorepo Structure

The project uses a pnpm workspace with Turborepo for the Node.js packages:

- `pnpm-workspace.yaml` defines `packages/*` as workspace members
- `turbo.json` defines build/dev/lint/test/typecheck tasks with dependency ordering
- `@els/shared` is a dependency of all API and frontend packages
- Python code (`src/`, `tests/`) is managed separately via `pyproject.toml`
