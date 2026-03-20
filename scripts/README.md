# Testing Scripts

This directory contains manual testing scripts and deployment tools for the ELS pipeline.

## Deployment Script

### deploy.sh

Automated deployment script for the ELS Pipeline infrastructure with country code support.

**Usage:**

```bash
# Deploy to dev environment (default)
./scripts/deploy.sh

# Deploy to staging
./scripts/deploy.sh -e staging

# Deploy to production in specific region
./scripts/deploy.sh -e prod -r us-west-2

# Show help
./scripts/deploy.sh --help
```

**Features:**

- Validates CloudFormation template
- Deploys infrastructure stack
- Creates environment-specific .env file with country-based path configuration
- Displays S3 path structure examples
- Verifies deployment success

**Requirements:**

- AWS CLI installed and configured
- Python 3.13+
- jq (for JSON parsing)
- Valid AWS credentials with deployment permissions

**Country Code Support:**
The deployment script configures the infrastructure to support multi-country deployments:

- S3 paths: `{country}/{state}/{year}/{identifier}`
- Standard IDs: `{country}-{state}-{year}-{domain}-{indicator}`
- Country codes validated against ISO 3166-1 alpha-2 format

## Manual Testing Scripts

All manual testing scripts now support country codes. When testing, use the country-based path structure:

- Raw documents: `{country}/{state}/{year}/{filename}`
- Processed JSON: `{country}/{state}/{year}/{standard_id}.json`

## Manual Ingester Test

### Prerequisites

1. **Deploy CloudFormation Stack**

   ```bash
   aws cloudformation deploy \
     --template-file infra/template.yaml \
     --stack-name els-pipeline-dev \
     --parameter-overrides EnvironmentName=dev \
     --capabilities CAPABILITY_NAMED_IAM
   ```

2. **Get the S3 Bucket Name**

   ```bash
   aws cloudformation describe-stacks \
     --stack-name els-pipeline-dev \
     --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
     --output text
   ```

3. **Set Environment Variables**

   Replace `<account-id>` with your AWS account ID from step 2:

   ```bash
   # For bash/zsh (macOS/Linux)
   export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
   export AWS_REGION="us-east-1"

   # To make it permanent, add to ~/.bashrc or ~/.zshrc:
   echo 'export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"' >> ~/.zshrc
   echo 'export AWS_REGION="us-east-1"' >> ~/.zshrc
   source ~/.zshrc
   ```

   For Windows PowerShell:

   ```powershell
   $env:ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
   $env:AWS_REGION="us-east-1"
   ```

4. **Verify AWS Credentials**
   ```bash
   aws sts get-caller-identity
   ```

### Running the Test

```bash
# From the project root directory
python scripts/test_ingester_manual.py
```

### Expected Output

```
============================================================
ELS Pipeline - Manual Ingester Test
============================================================

============================================================
Current Configuration:
============================================================
S3 Raw Bucket:  els-raw-documents-dev-123456789012
AWS Region:     us-east-1
============================================================

Testing California Standards Ingestion
------------------------------------------------------------
📄 File: standards/california_all_standards_2021.pdf
📊 Size: 1,234,567 bytes (1.18 MB)

🚀 Starting ingestion...

============================================================
Ingestion Result:
============================================================
Status:      success
S3 Key:      CA/2021/california_all_standards_2021.pdf
Version ID:  abc123xyz...

Metadata:
  state               : CA
  version_year        : 2021
  source_url          : https://www.cde.ca.gov/sp/cd/re/documents/ptklfataglance.pdf
  publishing_agency   : California Department of Education
  upload_timestamp    : 2026-02-10T12:34:56.789Z
============================================================

✅ SUCCESS! Document uploaded to S3.

Verification commands:
  aws s3 ls s3://els-raw-documents-dev-123456789012/CA/2021/california_all_standards_2021.pdf
  aws s3api head-object --bucket els-raw-documents-dev-123456789012 --key CA/2021/california_all_standards_2021.pdf
```

### Verification

After successful upload, verify the file in S3:

```bash
# List the file
aws s3 ls s3://els-raw-documents-dev-<account-id>/CA/2021/

# Get object metadata
aws s3api head-object \
  --bucket els-raw-documents-dev-<account-id> \
  --key CA/2021/california_all_standards_2021.pdf

# Download the file to verify content
aws s3 cp \
  s3://els-raw-documents-dev-<account-id>/CA/2021/california_all_standards_2021.pdf \
  /tmp/downloaded.pdf
```

### Troubleshooting

**Error: "NoSuchBucket"**

- Verify the bucket name is correct
- Ensure CloudFormation stack deployed successfully
- Check the ELS_RAW_BUCKET environment variable

**Error: "AccessDenied"**

- Verify AWS credentials are configured: `aws sts get-caller-identity`
- Ensure your IAM user/role has S3 permissions
- Check bucket policy and IAM policies

**Error: "File not found"**

- Ensure `standards/california_all_standards_2021.pdf` exists
- Run from the project root directory

**Error: "InvalidBucketName"**

- Bucket names must be lowercase
- Check for typos in the bucket name
- Verify the bucket was created by CloudFormation

## Integration Tests (Local)

For local testing without AWS, use the integration tests with moto:

```bash
# Install moto if not already installed
pip install moto[s3]

# Run integration tests
pytest tests/integration/test_ingester_integration.py -v

# Run with coverage
pytest tests/integration/test_ingester_integration.py --cov=els_pipeline.ingester
```

These tests use mocked S3 and don't require AWS credentials or deployed infrastructure.
