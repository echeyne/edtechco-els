# Scripts

Deployment scripts and manual testing tools for the ELS pipeline.

## Deployment Scripts

| Script                   | Description                                                                 |
| ------------------------ | --------------------------------------------------------------------------- |
| `deploy_els_pipeline.sh` | Deploy the core pipeline stack (S3, Lambda, Step Functions, Aurora) via CDK |
| `deploy_els_app.sh`      | Deploy the Standards Explorer app (API + frontend) via CDK                  |
| `deploy_planning_app.sh` | Deploy the Planning app (API + AgentCore + frontend) via CDK                |
| `deploy_landing_site.sh` | Deploy the landing site (frontend) via CDK                                  |
| `package_lambda.sh`      | Package Python Lambda code (used internally by older workflows)             |
| `migrate_cfn_to_cdk.sh`  | One-time migration helper from CloudFormation to CDK                        |

All deploy scripts support `-e` (environment), `-r` (region), `--skip-infra`, `--skip-frontend`, `--skip-api`, and `-h` (help). See [Deployment Guide](../documentation/DEPLOYMENT.md) for full usage.

## Manual Testing Scripts

These scripts test pipeline stages against real deployed AWS infrastructure. They require environment variables to be set (see `.env.example`).

| Script                     | What It Tests                                        |
| -------------------------- | ---------------------------------------------------- |
| `test_ingester_manual.py`  | Uploads a PDF to S3 with metadata tags               |
| `test_extractor_manual.py` | Runs Textract on an uploaded document                |
| `test_detector_manual.py`  | Runs Bedrock Claude structure detection              |
| `test_parser_manual.py`    | Runs hierarchy parsing on detected elements          |
| `test_validator_manual.py` | Validates and stores canonical JSON                  |
| `test_db_manual.py`        | Tests Aurora PostgreSQL persistence                  |
| `test_pipeline_manual.py`  | Runs the full pipeline end-to-end via Step Functions |

### Running Manual Tests

```bash
# Set environment variables
source .env  # or export them individually

# Run a specific test
python scripts/test_ingester_manual.py
python scripts/test_pipeline_manual.py
```

### Prerequisites

- Deployed pipeline stack (`./scripts/deploy_els_pipeline.sh`)
- Environment variables set (bucket names, region, database credentials)
- AWS credentials configured
- Sample PDF in `standards/` directory
