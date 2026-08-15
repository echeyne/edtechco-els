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

   The returned `canonical_level` of each depth is then rewritten deterministically by `canonicalize_depth_map_levels` — it is a pure function of a depth's POSITION, never the document's label words. Levels fill from the top down and drop from the bottom of the middle: first depth `domain`, deepest `indicator`, the depth directly under domain `strand`, anything between that and the leaf `sub_strand`. So a **3-level document is `domain > strand > indicator`** and has no sub-strand (e.g. CO), and a 2-level document is `domain > indicator`. This is enforced in Python because the prompt alone left the mapping to the model's discretion.

   The depth map's free-text `notes` field is deliberately **restricted to the level skeleton** (column layouts, running headers). It must not characterize body text below the deepest depth as "examples"/"illustrations", and must not tell Pass 2 to ignore anything. Pass 2 reads the depth map as authoritative, so an editorializing note is obeyed as an instruction: a Haiku note reading *"each indicator is followed by concrete examples"* caused Pass 2 to silently empty every AZ `indicator.description` (45/45 → 8/45). The Pass-2 prompt additionally scopes the depth map's authority to `level` assignment only, and rule 2a decides ownership from the chunk's own layout regardless of what `notes` says.
2. **Pass 2 — per-chunk extraction**: blocks are chunked with token overlap (`chunk_text_blocks`) and each chunk is sent to the detector model (`BEDROCK_DETECTOR_LLM_MODEL_ID`, default Claude Opus) along with the depth map, so the model classifies elements by document depth rather than re-guessing per chunk. Elements re-emitted at overlapping chunk boundaries are collapsed by `_dedup_elements`.

Each element is classified as a domain, strand, sub-strand, or indicator with a confidence score. The score is kept on `DetectedElement` as metadata only — there is no confidence gate; every element flows through to parsing and persistence, since every element gets reviewed by a human downstream regardless of confidence.

The detection prompt instructs the LLM to extract structured JSON with fields: level, code, title, description, confidence, source_page, source_text, and age_band (populated for indicators that come from age-banded columns, e.g. "Early (3 to 4 ½ Years)", "PK3").

`description` and `age_band` are both optional and both spell absence as `null`, never `""` — most headings own no prose of their own, so a null description is the common case rather than an error. `models._blank_to_none` enforces that on every optional free-text field at model-construction time (see [CLAUDE.md](../CLAUDE.md)), so the same absence cannot arrive under two spellings and reach Aurora's nullable `description` columns as an empty string.

#### Where an element's `code` comes from

Prompt rule 4 prefers a code the **document prints** and only invents one as a last resort. It names three places a printed code can live and searches them in order: **inline** on the heading line (`1.0`, `I.A.2`, `Benchmark 1.1`, a list letter `a`), **in a caption beside the heading** (a parenthetical, caption line, or table header — a group titled "Working Memory" captioned `Indicators (CD.WM)` has code `CD.WM`), and **as the shared leading prefix of its descendants' codes** — an ancestor's code is the common prefix of its descendants' document codes, so indicators reading `CD.WM.PK1`/`CD.WM.PK2`/`CD.AT.PK1` give the groups above them `CD.WM` and `CD.AT` and the level above those `CD`. The prefix is peeled one whole segment per level going up (a level printing its own code takes it and consumes no segment), so it can cross a level the printed namespace skips without over-reaching in a chunk that shows only one group. Only when all three come up empty does the model derive a ≤5-char uppercase abbreviation from the title (`Approaches to Learning` → `AL`, `Engages in an activity for a sustained period of time` → `EASPT`).

The recovery clause is prompt-only and has no Python counterpart: it reasons over page layout and over which codes in a chunk descend from which heading, neither of which is visible in the emitted JSON. It is guarded inside the prompt by shape alone — a descendant code needs more than one dot-separated segment, two descendants must agree on the prefix and differ after it, only whole segments count, and a descendant code carrying a structural label word (`Foundation 1.7`, `Benchmark 1.1`) is not a namespace path, since the label names the descendant's own level.

That derivation is a deterministic string algorithm, so `_resolve_code` re-executes it in Python via `derive_code_from_title` rather than trusting the sampled answer. It is scoped to the invented branch by two guards: the code's **shape** must be one the abbreviation branch could have produced (uppercase letters only — a digit, separator or lowercase letter means a positional document code, including a lettered leaf's `a`), and the code must be **ungrounded** — `_is_code_grounded` checks whether it appears in the element's own `source_text`, since a document code was transcribed off the page and an invented abbreviation was not. A printed code is authoritative and is never overwritten.

Grounding is what couples the two halves. A code recovered from a caption or a descendant prefix is short and uppercase (`T`, `SS`), so it has the abbreviation branch's shape and would be recomputed from the title unless it appears in the element's `source_text`. Rule 4 therefore requires the line that supplied the code to be cited in `source_text` alongside the heading line — which rule 7 already asks for, and which leaves rule 1's "a child's line alone is not evidence of the heading" self-check intact.

The reason is reproducibility of the primary key. Three detector runs at temperature 0 over one frozen Kentucky extraction gave 11 of 44 elements (25%) a different code on at least one run — one run emitting a 4-character code, another transposing two initials, several keeping a connector word the rule excludes — while `level`, `source_page` and `age_band` never varied. Because `standard_id` is `{country}-{state}-{year}-{indicator_code}`, that churn is a different Aurora primary key for the same standard on each run. The rule stays in the prompt and the Python executes it; see the LLM-first design note in [CLAUDE.md](../CLAUDE.md) for why this pairing is the sanctioned shape and a per-state abbreviation branch is not.

#### Layout coordinates in the prompt

Textract records a normalized bounding box for every block, but a page-only serialization (`[Page 12] …`) throws that away — and on a multi-column page the blocks arrive interleaved line by line, so the model has no way to tell which column a line came from and crosses their contents. `_serialize_blocks_for_prompt` therefore tags each prompt line with its normalized left edge: `[Page 12 | x=0.09] …`.

The coordinate is passed through raw and the **model** groups lines into columns; `_block_left` only reads `BoundingBox.Left` off the block and validates its range. Clustering the edges in Python was tried and deliberately rejected: it would decide the document's layout on the model's behalf, and a mis-clustered line reaches the model as wrong evidence it cannot recover from — the opposite of the LLM-first direction in [CLAUDE.md](../CLAUDE.md). Blocks whose geometry is missing or degenerate emit the plain `[Page N]` tag.

Blocks stay in **document order** rather than being re-sorted into column order: `chunk_text_blocks` slices this same sequence into overlapping chunks, so re-ordering would separate a column's head from its tail, and row adjacency is what ties the columns of one age-band row together. The tag carries the signal without moving anything.

#### Overlap de-duplication

`_dedup_elements` handles the two shapes a chunk boundary produces. An element may be emitted **whole twice** under drifting codes (one domain arriving as both `SED` and `I`), or **once truncated and once complete** — chunk N ran out of text mid-sentence while chunk N+1 saw the element whole. Codes are reconciled first, by the same `parser.normalize_element_codes` machinery the parser uses, which collapses the first shape; the second is collapsed by prefix dominance, keeping the longer title and the richer description.

Age-band spellings are reconciled before either pass, by `_reconcile_age_band_drift`. Both passes key identity on `age_band`, so one column read as `PK3` in chunk N and `PK3 Outcome` in chunk N+1 would otherwise survive as two elements no matter what the rest of the function does — and downstream those become separate standards colliding on `standard_id` (observed on TX as four collisions across 29 standards holding 25 distinct keys). A fold requires both a token-prefix relationship between the two labels and an otherwise-identical element carrying both, so genuinely distinct bands that merely share a prefix are left alone.

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

| Shape            | Where it goes | Example                                                  |
| ---------------- | ------------- | -------------------------------------------------------- |
| Age prefix       | Leading       | TX `PK3.I.A.2` vs `PK4.I.A.2`                            |
| Column suffix    | Trailing      | CA `ELD.1.0.VOC.1.1.DISC` vs `ELD.1.0.VOC.1.1.BRD`       |
| Ancestor segment | Spliced in    | NV `SS.2.CI.PK3` vs `SS.5.CI.PK3`                        |

The first two keep side-by-side age/proficiency columns from collapsing into a
single ID. The third handles a different failure: a document whose **printed
code namespace is not unique**. Nevada codes its indicators
`<domain>.<sub_strand>.PKn`, skipping the strand — so two genuinely different
standards both print `SS.CI.PK3` ("resolve conflicts with peers *with adult
guidance*" under Social Studies Standard 5, and "*in an age-appropriate
manner*" under Standard 2), and the strand is the only thing separating them.

`disambiguate_colliding_standards` (in `parser.py`) resolves this after all
chunks merge, ancestor-first: colliding rows are re-qualified with their own
parent's segments. **Every member of the colliding set is rewritten, including
the first one seen**, so the ids do not depend on which row was parsed first —
the same document always yields the same keys. A numeric counter remains only
as a fallback for rows no parent can separate; that path *is* order-dependent
and logs a warning saying so.

It runs after the merge rather than inside the per-chunk loop for two reasons:
a collision can span two chunks, and `normalize_parsed_codes` can itself bring
two rows onto one code.

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
