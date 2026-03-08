# Testing Guide

The ELS pipeline uses a three-tier testing strategy for every component:

1. **Property-based tests** — Verify universal correctness properties using Hypothesis
2. **Integration tests** — Test components with mocked AWS services using moto
3. **Manual AWS tests** — Verify functionality against real deployed infrastructure

## Running Tests

```bash
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
```

### Manual AWS Tests (requires deployment)

```bash
python scripts/test_ingester_manual.py
python scripts/test_extractor_manual.py
python scripts/test_detector_manual.py
python scripts/test_parser_manual.py
python scripts/test_validator_manual.py
python scripts/test_db_manual.py
python scripts/test_pipeline_manual.py
```

## Component Coverage

| Component    | Property Tests                                                                    | Integration Tests | Manual Test      |
| ------------ | --------------------------------------------------------------------------------- | ----------------- | ---------------- |
| Ingester     | S3 path construction, metadata completeness, format validation                    | Mocked S3         | Real S3 upload   |
| Extractor    | Block reading order, table cell structure, page numbers                           | Mocked Textract   | Real Textract    |
| Detector     | Confidence threshold flagging                                                     | Mocked Bedrock    | Real Bedrock LLM |
| Parser       | Level normalization, hierarchy mapping, Standard_ID determinism, orphan detection | Logic testing     | Sample data      |
| Validator    | Schema validation, error reporting, uniqueness, serialization round-trip          | Mocked S3         | Real S3 storage  |
| Database     | Vector similarity ordering, query filter correctness                              | Test DB           | Real Aurora      |
| Orchestrator | Stage result completeness, run count invariants                                   | Mocked stages     | Step Functions   |

## Environment Setup

### Local (no AWS required)

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### AWS Testing (after deployment)

```bash
# Get bucket names from stack outputs
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
export BEDROCK_PARSER_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-6
export BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

export CONFIDENCE_THRESHOLD=0.7
```

See `.env.example` for the full list.

## Coverage Goals

- Overall: > 80%
- Critical paths (ingestion, validation, embeddings, DB): > 90%
- All 27 correctness properties covered by property tests
- All AWS service interactions covered by integration tests

## Debugging

```bash
pytest tests/ -vv          # Verbose output
pytest tests/ -x           # Stop on first failure
pytest tests/ --pdb        # Drop into debugger on failure
pytest tests/ -s           # Show print statements
```

## Troubleshooting

| Issue                               | Fix                                                       |
| ----------------------------------- | --------------------------------------------------------- |
| `ModuleNotFoundError: els_pipeline` | `pip install -e .`                                        |
| `NoSuchBucket`                      | Check `ELS_RAW_BUCKET` env var and CloudFormation outputs |
| `AccessDenied`                      | Verify credentials: `aws sts get-caller-identity`         |
| Property tests timeout              | `pytest tests/property/ --hypothesis-max-examples=10`     |
| moto not installed                  | `pip install 'moto[s3,textract,bedrock]'`                 |

## Related

- [Deployment Guide](DEPLOYMENT.md)
- [AWS Operations Guide](AWS_TESTING.md)
- [Scripts README](../scripts/README.md)
