# Comprehensive Testing Guide for ELS Pipeline

This guide covers the complete testing strategy for all components of the ELS Normalization Pipeline.

## Testing Philosophy

The ELS pipeline uses a three-tier testing approach for every component:

1. **Property-Based Tests** - Verify universal correctness properties using Hypothesis
2. **Integration Tests** - Test components with mocked AWS services using moto
3. **Manual AWS Tests** - Verify functionality with real AWS infrastructure

## Quick Reference

### Run All Tests Locally

```bash
# All tests (property + integration)
pytest tests/ -v

# By test type
pytest tests/property/ -v          # Property-based tests only
pytest tests/integration/ -v       # Integration tests only

# With coverage
pytest tests/ --cov=els_pipeline --cov-report=html
open htmlcov/index.html
```

### Run Manual AWS Tests

```bash
# Individual components (after deployment)
python scripts/test_ingester_manual.py
python scripts/test_extractor_manual.py
python scripts/test_detector_manual.py
python scripts/test_parser_manual.py
python scripts/test_validator_manual.py
python scripts/test_embedder_manual.py
python scripts/test_db_manual.py
python scripts/test_recommender_manual.py

# Full pipeline
python scripts/test_pipeline_manual.py
```

## Component Testing Matrix

| Component    | Property Tests      | Integration Tests   | Manual AWS Test         |
| ------------ | ------------------- | ------------------- | ----------------------- |
| Ingester     | ✅ Properties 1-3   | ✅ S3 mocking       | ✅ Real S3 upload       |
| Extractor    | ✅ Properties 4-6   | ✅ Textract mocking | ✅ Real Textract        |
| Detector     | ✅ Property 8       | ✅ Bedrock mocking  | ✅ Real Bedrock LLM     |
| Parser       | ✅ Properties 9-12  | ✅ Logic testing    | ✅ Sample data          |
| Validator    | ✅ Properties 13-16 | ✅ S3 mocking       | ✅ Real S3 storage      |
| Embedder     | ✅ Properties 17-18 | ✅ Bedrock mocking  | ✅ Real embeddings      |
| Database     | ✅ Properties 19-20 | ✅ Test DB          | ✅ Real Aurora          |
| Recommender  | ✅ Properties 21-25 | ✅ Bedrock mocking  | ✅ Real recommendations |
| Orchestrator | ✅ Properties 26-27 | ✅ Stage mocking    | ✅ Step Functions       |

## Detailed Component Testing

### 1. Raw Document Ingester

**Files:**

- Implementation: `src/els_pipeline/ingester.py`
- Property tests: `tests/property/test_ingestion_props.py`
- Integration tests: `tests/integration/test_ingester_integration.py`
- Manual test: `scripts/test_ingester_manual.py`

**Property Tests:**

- Property 1: S3 Path Construction
- Property 2: Ingestion Metadata Completeness
- Property 3: Format Validation Correctness

**Run Tests:**

```bash
# Run all tests
pytest tests/ -v

# Property tests only
pytest tests/property/test_ingestion_props.py -v

# Integration tests only (uses mocked S3)
pytest tests/integration/test_ingester_integration.py -v

# With coverage
pytest tests/ --cov=els_pipeline.ingester --cov-report=term-missing

# Manual AWS test (requires deployment)
export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
export AWS_REGION="us-east-1"
python scripts/test_ingester_manual.py
```

**What's Tested:**

- ✅ PDF and HTML format acceptance
- ✅ Unsupported format rejection
- ✅ S3 path construction pattern
- ✅ Metadata completeness
- ✅ S3 versioning
- ✅ Error handling (file not found, access denied)

**File Naming Convention:**

The ingester accepts any filename with supported extensions (`.pdf` or `.html`).

Recommended convention:

```
{state_name}_{document_type}_{year}.{ext}

Examples:
- california_all_standards_2021.pdf
- california_foundations_2021.pdf
- texas_guidelines_2022.pdf
- new_york_standards_2023.html
```

S3 path structure:

```
{state}/{year}/{filename}

Examples:
- CA/2021/california_all_standards_2021.pdf
- TX/2022/texas_guidelines_2022.pdf
- NY/2023/new_york_standards_2023.html
```

**Verification After Upload:**

Using AWS CLI:

```bash
# List files in bucket
aws s3 ls s3://els-raw-documents-dev-<account-id>/CA/2021/

# Get object metadata
aws s3api head-object \
  --bucket els-raw-documents-dev-<account-id> \
  --key CA/2021/california_all_standards_2021.pdf

# Download file to verify
aws s3 cp \
  s3://els-raw-documents-dev-<account-id>/CA/2021/california_all_standards_2021.pdf \
  /tmp/downloaded.pdf

# List all versions (if versioning enabled)
aws s3api list-object-versions \
  --bucket els-raw-documents-dev-<account-id> \
  --prefix CA/2021/california_all_standards_2021.pdf
```

Using AWS Console:

1. Navigate to S3 in AWS Console
2. Find bucket: `els-raw-documents-dev-<account-id>`
3. Browse to: `CA/2021/`
4. Click on file to view metadata and properties
5. Click "Versions" tab to see version history

---

### 2. Text Extractor

**Files:**

- Implementation: `src/els_pipeline/extractor.py`
- Property tests: `tests/property/test_extraction_props.py`
- Integration tests: `tests/integration/test_extractor_integration.py`
- Manual test: `scripts/test_extractor_manual.py`

**Property Tests:**

- Property 4: Text Block Reading Order
- Property 5: Table Cell Structure Preservation
- Property 6: Page Number Presence

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_extraction_props.py -v

# Integration tests
pytest tests/integration/test_extractor_integration.py -v

# Manual AWS test
python scripts/test_extractor_manual.py
```

**What's Tested:**

- ✅ Textract API integration
- ✅ Block reading order (page, top, left)
- ✅ Table cell structure preservation
- ✅ Page number tracking
- ✅ Async/sync handling for large/small docs
- ✅ Error handling for empty responses

---

### 3. Structure Detector

**Files:**

- Implementation: `src/els_pipeline/detector.py`
- Property tests: `tests/property/test_detection_props.py`
- Integration tests: `tests/integration/test_detector_integration.py`
- Manual test: `scripts/test_detector_manual.py`

**Property Tests:**

- Property 8: Confidence Threshold Flagging

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_detection_props.py -v

# Integration tests
pytest tests/integration/test_detector_integration.py -v

# Manual AWS test
export BEDROCK_DETECTOR_LLM_MODEL_ID="us.anthropic.claude-opus-4-6-v1"
python scripts/test_detector_manual.py
```

**What's Tested:**

- ✅ Bedrock LLM integration
- ✅ Text chunking with overlap
- ✅ JSON response parsing
- ✅ Confidence threshold flagging (< 0.7 = needs_review)
- ✅ Retry logic for malformed responses
- ✅ Element classification accuracy

---

### 4. Hierarchy Parser

**Files:**

- Implementation: `src/els_pipeline/parser.py`
- Property tests: `tests/property/test_parsing_props.py`
- Integration tests: `tests/integration/test_parser_integration.py`
- Manual test: `scripts/test_parser_manual.py`

**Property Tests:**

- Property 9: Canonical Level Normalization
- Property 10: Depth-Based Hierarchy Mapping
- Property 11: Standard_ID Determinism
- Property 12: No Orphaned Indicators

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_parsing_props.py -v

# Integration tests
pytest tests/integration/test_parser_integration.py -v

# Manual test
python scripts/test_parser_manual.py
```

**What's Tested:**

- ✅ Depth normalization (2, 3, 4+ levels)
- ✅ Standard_ID generation format
- ✅ Standard_ID determinism
- ✅ Orphan detection
- ✅ Tree assembly
- ✅ Canonical level mapping

---

### 5. Validator

**Files:**

- Implementation: `src/els_pipeline/validator.py`
- Property tests: `tests/property/test_validation_props.py`
- Integration tests: `tests/integration/test_validator_integration.py`
- Manual test: `scripts/test_validator_manual.py`

**Property Tests:**

- Property 13: Schema Validation Rejects Invalid Records
- Property 14: Validation Error Reporting
- Property 15: Standard_ID Uniqueness Enforcement
- Property 16: Serialization Round Trip

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_validation_props.py -v

# Integration tests
pytest tests/integration/test_validator_integration.py -v

# Manual AWS test
export ELS_PROCESSED_BUCKET="els-processed-json-dev-<account-id>"
python scripts/test_validator_manual.py
```

**What's Tested:**

- ✅ JSON schema validation
- ✅ Required field checking
- ✅ Null strand/sub_strand handling
- ✅ Standard_ID uniqueness
- ✅ Serialization/deserialization round-trip
- ✅ S3 storage of validated records
- ✅ Error collection (all errors, not just first)

---

### 6. Embedding Generator

**Files:**

- Implementation: `src/els_pipeline/embedder.py`
- Property tests: `tests/property/test_embedding_props.py`
- Integration tests: `tests/integration/test_embedder_integration.py`
- Manual test: `scripts/test_embedder_manual.py`

**Property Tests:**

- Property 17: Embedding Input Text Construction
- Property 18: Embedding Record Completeness

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_embedding_props.py -v

# Integration tests
pytest tests/integration/test_embedder_integration.py -v

# Manual AWS test
export ELS_EMBEDDINGS_BUCKET="els-embeddings-dev-<account-id>"
export BEDROCK_EMBEDDING_MODEL_ID="amazon.titan-embed-text-v1"
python scripts/test_embedder_manual.py
```

**What's Tested:**

- ✅ Input text construction (domain + strand + sub_strand + indicator + age)
- ✅ Null level omission
- ✅ Bedrock Titan Embed integration
- ✅ Vector generation
- ✅ S3 storage
- ✅ Database persistence
- ✅ Embedding record completeness

---

### 7. Data Access Layer

**Files:**

- Implementation: `src/els_pipeline/db.py`
- Property tests: `tests/property/test_db_props.py`
- Integration tests: `tests/integration/test_db_integration.py`
- Manual test: `scripts/test_db_manual.py`

**Property Tests:**

- Property 19: Vector Similarity Ordering
- Property 20: Query Filter Correctness

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_db_props.py -v

# Integration tests (requires test database)
docker-compose up -d postgres
pytest tests/integration/test_db_integration.py -v

# Manual AWS test
export DB_HOST="<aurora-endpoint>"
export DB_PASSWORD="<from-secrets-manager>"
python scripts/test_db_manual.py
```

**What's Tested:**

- ✅ Database connection management
- ✅ CRUD operations (standards, embeddings, recommendations)
- ✅ pgvector cosine similarity search
- ✅ Query filters (state, age_band, domain, version_year)
- ✅ Result ordering by similarity
- ✅ Connection pooling

---

### 8. Recommendation Generator

**Files:**

- Implementation: `src/els_pipeline/recommender.py`
- Property tests: `tests/property/test_recommendation_props.py`
- Integration tests: `tests/integration/test_recommender_integration.py`
- Manual test: `scripts/test_recommender_manual.py`

**Property Tests:**

- Property 21: Recommendation Audience Coverage
- Property 22: Recommendation Prompt Context
- Property 23: Recommendation Record Completeness
- Property 24: Actionability Validation
- Property 25: Recommendation State Scoping

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_recommendation_props.py -v

# Integration tests
pytest tests/integration/test_recommender_integration.py -v

# Manual AWS test
python scripts/test_recommender_manual.py
```

**What's Tested:**

- ✅ LLM prompt construction
- ✅ Audience coverage (parent + teacher)
- ✅ Actionability checking (action verb + specific noun)
- ✅ Retry logic for non-actionable responses
- ✅ State scoping
- ✅ Domain/strand aggregation
- ✅ Database persistence

---

### 9. Pipeline Orchestrator

**Files:**

- Implementation: `src/els_pipeline/orchestrator.py`
- Property tests: `tests/property/test_orchestrator_props.py`
- Integration tests: `tests/integration/test_orchestrator_integration.py`
- Manual test: `scripts/test_pipeline_manual.py`

**Property Tests:**

- Property 26: Pipeline Stage Result Completeness
- Property 27: Pipeline Run Counts Invariant

**Run Tests:**

```bash
# Property tests
pytest tests/property/test_orchestrator_props.py -v

# Integration tests
pytest tests/integration/test_orchestrator_integration.py -v

# Manual AWS test (Step Functions)
python scripts/test_pipeline_manual.py
```

**What's Tested:**

- ✅ Stage chaining (ingestion → extraction → ... → persistence)
- ✅ Stage result recording
- ✅ Error handling and partial results
- ✅ Count invariants (validated ≤ indicators, embedded ≤ validated)
- ✅ Stage re-run capability
- ✅ Status tracking
- ✅ SNS notifications

---

## Environment Setup

### Local Testing (No AWS)

```bash
# Install dependencies
pip install -e .
pip install 'moto[s3,textract,bedrock]' pytest-cov

# Run tests
pytest tests/ -v
```

### AWS Testing (After Deployment)

```bash
# 1. Deploy infrastructure
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name els-pipeline-dev \
  --parameter-overrides EnvironmentName=dev \
  --capabilities CAPABILITY_NAMED_IAM

# 2. Get bucket name from outputs
aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
  --output text

# 3. Set environment variables (replace <account-id> with your AWS account ID)
export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
export ELS_PROCESSED_BUCKET="els-processed-json-dev-<account-id>"
export ELS_EMBEDDINGS_BUCKET="els-embeddings-dev-<account-id>"
export DB_HOST="<from-outputs>"
export DB_PASSWORD="<from-secrets-manager>"
export AWS_REGION="us-east-1"

# 4. Run manual tests
python scripts/test_ingester_manual.py
# ... etc
```

**Making Environment Variables Permanent:**

macOS/Linux (bash/zsh):

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export ELS_RAW_BUCKET="els-raw-documents-dev-123456789012"' >> ~/.zshrc
echo 'export AWS_REGION="us-east-1"' >> ~/.zshrc
source ~/.zshrc
```

Windows PowerShell:

```powershell
# Set for current session
$env:ELS_RAW_BUCKET="els-raw-documents-dev-123456789012"
$env:AWS_REGION="us-east-1"

# Set permanently (requires admin)
[System.Environment]::SetEnvironmentVariable('ELS_RAW_BUCKET', 'els-raw-documents-dev-123456789012', 'User')
[System.Environment]::SetEnvironmentVariable('AWS_REGION', 'us-east-1', 'User')
```

### Environment Variables Reference

```bash
# S3 Buckets
export ELS_RAW_BUCKET="els-raw-documents-dev-123456789012"
export ELS_PROCESSED_BUCKET="els-processed-json-dev-123456789012"
export ELS_EMBEDDINGS_BUCKET="els-embeddings-dev-123456789012"

# AWS Configuration
export AWS_REGION="us-east-1"

# Bedrock Models
export BEDROCK_DETECTOR_LLM_MODEL_ID=us.anthropic.claude-opus-4-6-v1
export BEDROCK_PARSER_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-6
export BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Database
export DB_HOST="els-cluster.cluster-xxxxx.us-east-1.rds.amazonaws.com"
export DB_PORT="5432"
export DB_NAME="els_corpus"
export DB_USER="postgres"
export DB_PASSWORD="<from-secrets-manager>"

# Pipeline Configuration
export CONFIDENCE_THRESHOLD="0.7"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: ELS Pipeline Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.9"

      - name: Install dependencies
        run: |
          pip install -e .
          pip install 'moto[s3,textract,bedrock]' pytest-cov

      - name: Run property tests
        run: pytest tests/property/ -v --cov=els_pipeline

      - name: Run integration tests
        run: pytest tests/integration/ -v --cov=els_pipeline --cov-append

      - name: Generate coverage report
        run: pytest --cov=els_pipeline --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Test Coverage Goals

- **Overall coverage:** > 80%
- **Critical paths:** > 90%
  - Ingestion
  - Validation
  - Embedding generation
  - Database operations
- **Property tests:** All 27 correctness properties
- **Integration tests:** All AWS service interactions
- **Manual tests:** All deployed components

### Check Coverage

```bash
# Generate HTML report
pytest tests/ --cov=els_pipeline --cov-report=html

# Open in browser
open htmlcov/index.html

# Terminal report with missing lines
pytest tests/ --cov=els_pipeline --cov-report=term-missing
```

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'els_pipeline'"**

```bash
# Install package in development mode
pip install -e .
```

**"NoSuchBucket" Error**

- Verify bucket name: `aws s3 ls | grep els-raw`
- Check CloudFormation outputs
- Verify ELS_RAW_BUCKET environment variable

**"AccessDenied" Error**

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify IAM permissions
aws iam get-user
```

**"File not found" Error**

- Ensure you're running from project root
- Verify file exists: `ls -la standards/california_all_standards_2021.pdf`

**Tests Fail with Import Errors**

```bash
# Reinstall package
pip install -e .

# Verify installation
python -c "from els_pipeline.ingester import ingest_document; print('OK')"
```

**Moto not installed:**

```bash
pip install 'moto[s3,textract,bedrock]'
```

**Property tests timeout:**

```bash
pytest tests/property/ --hypothesis-max-examples=10
```

**Database connection fails:**

```bash
# Start test database
docker-compose up -d postgres

# Check connection
psql -h localhost -U postgres -d els_corpus
```

### Debugging

```bash
# Verbose output
pytest tests/ -vv

# Stop on first failure
pytest tests/ -x

# Run with debugger
pytest tests/ --pdb

# Show print statements
pytest tests/ -s

# Run specific test
pytest tests/integration/test_ingester_integration.py::test_ingester_with_mocked_s3_success -vv
```

## Next Steps

1. ✅ Run local tests for each component as you implement
2. ✅ Ensure all property tests pass
3. ✅ Verify integration tests with mocked services
4. ✅ Deploy infrastructure to AWS
5. ✅ Run manual AWS tests to verify deployment
6. ✅ Set up CI/CD for automated testing
7. ✅ Monitor coverage and add tests for gaps

## Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - Infrastructure deployment
- [Scripts README](../scripts/README.md) - Manual test script usage
- [Design Document](../.kiro/specs/els-normalization-pipeline/design.md) - Correctness properties
