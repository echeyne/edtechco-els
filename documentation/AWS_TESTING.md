# AWS Deployment and Testing Guide - ELS Normalization Pipeline

## Overview

This guide provides step-by-step instructions for deploying and testing the ELS Normalization Pipeline on AWS. The pipeline processes early learning standards documents from multiple countries and states, normalizing them into a consistent format with country-based path structures.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Instructions](#deployment-instructions)
3. [Post-Deployment Verification](#post-deployment-verification)
4. [Testing the Core Pipeline](#testing-the-core-pipeline)
5. [Monitoring and Logging](#monitoring-and-logging)
6. [Troubleshooting](#troubleshooting)
7. [Cost Optimization](#cost-optimization)

---

## Pre-Deployment Checklist

### Prerequisites

Before deploying the ELS pipeline, ensure you have:

- [ ] AWS CLI installed and configured (version 2.x or later)
- [ ] Python 3.11 or later installed
- [ ] pip package manager installed
- [ ] Valid AWS credentials with appropriate permissions
- [ ] Access to the following AWS services:
  - S3
  - Lambda
  - Step Functions
  - Aurora PostgreSQL (Serverless v2)
  - Textract
  - Bedrock (with Claude Sonnet 4.5 and Titan Embed models enabled)
  - CloudWatch
  - SNS
  - Secrets Manager
  - IAM

### Required AWS Permissions

Your AWS user/role must have permissions to:

- Create and manage CloudFormation stacks
- Create and manage S3 buckets
- Create and manage Lambda functions and update function code
- Upload to S3 buckets (for Lambda code deployment)
- Create and manage Step Functions state machines
- Create and manage Aurora PostgreSQL clusters
- Create and manage IAM roles and policies
- Create and manage VPCs, subnets, and security groups
- Create and manage Secrets Manager secrets
- Create and manage SNS topics
- Invoke Bedrock models

### Bedrock Model Access

Ensure you have access to the following Bedrock models in your AWS region:

- `us.anthropic.claude-sonnet-4-6` (for structure detection and recommendations)
- `amazon.titan-embed-text-v2:0` (for embeddings)

To request model access:

1. Navigate to AWS Bedrock console
2. Go to "Model access" in the left sidebar
3. Request access for Claude Sonnet 4.5 and Titan Embed Text v2
4. Wait for approval (usually instant for Titan, may take time for Claude)

---

## Deployment Instructions

### Step 1: Clone and Prepare the Repository

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd els-pipeline

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Step 2: Configure Environment Variables

Create a `.env` file in the project root (or use the provided `.env.example` as a template):

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your preferred editor
nano .env
```

Required environment variables:

```bash
# AWS Configuration
AWS_REGION=us-east-1
ENVIRONMENT=dev  # or staging, prod

# Bedrock Model IDs
BEDROCK_DETECTOR_LLM_MODEL_ID=us.anthropic.claude-opus-4-6-v1
BEDROCK_PARSER_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-6
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Confidence Threshold
CONFIDENCE_THRESHOLD=0.7

# Country Code Validation
COUNTRY_CODE_VALIDATION=enabled
```

### Step 3: Validate CloudFormation Template

Before deploying, validate the CloudFormation template:

```bash
aws cloudformation validate-template \
  --template-body file://infra/template.yaml \
  --region us-east-1
```

Expected output: Template validation successful with parameters and capabilities listed.

### Step 4: Package Lambda Functions

The Lambda functions need to be packaged with their dependencies before deployment:

```bash
# Package Lambda functions and upload to S3
bash scripts/package_lambda.sh

# Or specify environment and region
ENVIRONMENT=dev AWS_REGION=us-east-1 bash scripts/package_lambda.sh
```

This script will:

- Install Python dependencies (boto3, pydantic, psycopg2-binary, python-dotenv)
- Copy source code from `src/els_pipeline/`
- Create a ZIP file with all dependencies
- Create an S3 bucket for Lambda code (if it doesn't exist): `els-lambda-code-{environment}-{account-id}`
- Upload the ZIP file to S3
- Update existing Lambda functions with the new code (if they exist)

Note: The deployment script (Step 5) automatically calls this packaging script, so you can skip this step if using the deployment script.

### Step 5: Deploy the Stack

Use the provided deployment script:

```bash
# Deploy to dev environment in us-east-1 (default)
./scripts/deploy.sh

# Deploy to staging environment in us-west-2
./scripts/deploy.sh -e staging -r us-west-2

# Deploy to production
./scripts/deploy.sh -e prod -r us-east-1
```

The deployment script will:

1. Check prerequisites (AWS CLI, Python, credentials)
2. Package Lambda functions (calls `package_lambda.sh`)
3. Validate the CloudFormation template
4. Deploy the stack with all resources
5. Display stack outputs (bucket names, ARNs, endpoints)
6. Create an environment-specific `.env` file
7. Verify deployment success

Deployment typically takes 10-15 minutes due to Aurora PostgreSQL cluster creation.

### Step 6: Note Stack Outputs

After deployment, save the following outputs for testing:

```bash
# Get all stack outputs
aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --region us-east-1 \
  --query 'Stacks[0].Outputs' \
  --output table
```

Key outputs:

- `RawDocumentsBucketName`: S3 bucket for raw documents
- `ProcessedJsonBucketName`: S3 bucket for processed JSON
- `DatabaseClusterEndpoint`: Aurora PostgreSQL endpoint
- `DatabaseSecretArn`: Secrets Manager ARN for database credentials
- `PipelineStateMachineArn`: Step Functions state machine ARN
- `PipelineNotificationTopicArn`: SNS topic for notifications
- `IngesterLambdaFunctionArn`: ARN of the Ingester Lambda function
- `TextExtractorLambdaFunctionArn`: ARN of the Text Extractor Lambda function
- `StructureDetectorLambdaFunctionArn`: ARN of the Structure Detector Lambda function
- `HierarchyParserLambdaFunctionArn`: ARN of the Hierarchy Parser Lambda function
- `ValidatorLambdaFunctionArn`: ARN of the Validator Lambda function
- `PersistenceLambdaFunctionArn`: ARN of the Persistence Lambda function

---

## Post-Deployment Verification

### Verify S3 Buckets

```bash
# List raw documents bucket
aws s3 ls s3://els-raw-documents-dev-<account-id>/

# List processed JSON bucket
aws s3 ls s3://els-processed-json-dev-<account-id>/

# Verify bucket versioning is enabled
aws s3api get-bucket-versioning \
  --bucket els-raw-documents-dev-<account-id>
```

Expected: Both buckets should exist and have versioning enabled.

### Verify Aurora PostgreSQL Cluster

```bash
# Check cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier els-database-cluster-dev \
  --region us-east-1 \
  --query 'DBClusters[0].Status'
```

Expected output: `"available"`

### Verify Lambda Functions

```bash
# List all ELS Lambda functions
aws lambda list-functions \
  --region us-east-1 \
  --query 'Functions[?starts_with(FunctionName, `els-`)].FunctionName'
```

Expected: List of Lambda functions for each pipeline stage (ingester, extractor, detector, parser, validator, persistence).

### Verify Step Functions State Machine

```bash
# Describe state machine
aws stepfunctions describe-state-machine \
  --state-machine-arn <PipelineStateMachineArn> \
  --region us-east-1
```

Expected: State machine should be in `ACTIVE` status.

### Verify Database Schema

```bash
# Connect to Aurora PostgreSQL
# First, get database credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id els-database-credentials-dev \
  --region us-east-1 \
  --query 'SecretString' \
  --output text

# Use the credentials to connect via psql
psql -h <DatabaseClusterEndpoint> \
     -U els_admin \
     -d els_pipeline \
     -c "\dt"
```

Expected: List of tables (documents, domains, strands, sub_strands, indicators, embeddings, recommendations, pipeline_runs, pipeline_stages).

---

## Testing the Core Pipeline

### Test 1: Document Ingestion

Upload a test document to the raw bucket:

```bash
# Create a test PDF (or use an existing one)
echo "Test ELS Document" > test_standards.txt

# Upload to S3 with country-based path structure
aws s3 cp test_standards.pdf \
  s3://els-raw-documents-dev-<account-id>/US/CA/2021/test_standards.pdf \
  --metadata country=US,state=CA,version_year=2021
```

Verify upload:

```bash
aws s3 ls s3://els-raw-documents-dev-<account-id>/US/CA/2021/
```

### Test 2: Manual Pipeline Execution

Start a pipeline execution using the Step Functions console or AWS CLI:

```bash
# Start execution
aws stepfunctions start-execution \
  --state-machine-arn <PipelineStateMachineArn> \
  --name "test-execution-$(date +%s)" \
  --input '{
    "run_id": "pipeline-US-CA-2021-test-001",
    "file_path": "US/CA/2021/test_standards.pdf",
    "country": "US",
    "state": "CA",
    "version_year": 2021,
    "source_url": "https://example.com/test_standards.pdf",
    "publishing_agency": "California Department of Education",
    "filename": "test_standards.pdf"
  }' \
  --region us-east-1
```

### Test 3: Monitor Execution

```bash
# Get execution status
aws stepfunctions describe-execution \
  --execution-arn <execution-arn> \
  --region us-east-1 \
  --query 'status'

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> \
  --region us-east-1 \
  --max-results 100
```

### Test 4: Verify Outputs

Check processed JSON bucket for both intermediate files and final canonical records:

```bash
# List all files for the test run
aws s3 ls s3://els-processed-json-dev-<account-id>/US/CA/2021/ --recursive

# Check intermediate files (see S3 Intermediate Data Storage section for details)
aws s3 ls s3://els-processed-json-dev-<account-id>/US/CA/2021/intermediate/ --recursive
```

Expected:

- Intermediate files in `intermediate/extraction/`, `intermediate/detection/`, `intermediate/parsing/`, and `intermediate/validation/` directories
- Final canonical JSON files with Standard_IDs following the pattern `US-CA-2021-{DOMAIN}-{INDICATOR}.json`

For detailed information on intermediate file formats and verification, see the [S3 Intermediate Data Storage](#s3-intermediate-data-storage) section.

### Test 5: Query Database

```bash
# Connect to database and query indicators
psql -h <DatabaseClusterEndpoint> \
     -U els_admin \
     -d els_pipeline \
     -c "SELECT standard_id, domain_id, indicator.code, indicator.description
         FROM indicators
         WHERE country = 'US' AND state = 'CA'
         LIMIT 10;"
```

### Test 6: Check SNS Notifications

```bash
# Subscribe to SNS topic for testing
aws sns subscribe \
  --topic-arn <PipelineNotificationTopicArn> \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-1

# Confirm subscription via email
# Then run a pipeline execution and check for notifications
```

---

## S3 Intermediate Data Storage

### Overview

The ELS pipeline uses S3 to store intermediate data between pipeline stages. This allows each Lambda function to persist its output and enables debugging by inspecting intermediate results at each stage.

### S3 Bucket Structure

All intermediate data is stored in the processed JSON bucket with the following structure:

```
els-processed-json-{env}-{account-id}/
├── {country}/{state}/{year}/
│   ├── intermediate/
│   │   ├── extraction/
│   │   │   └── {run_id}.json          # Textract blocks from extraction stage
│   │   ├── detection/
│   │   │   └── {run_id}.json          # Detected structure elements
│   │   ├── parsing/
│   │   │   └── {run_id}.json          # Parsed indicators with hierarchy
│   │   └── validation/
│   │       └── {run_id}.json          # Validation summary
│   └── {standard_id}.json             # Final canonical records
```

Example path for extraction output:

```
s3://els-processed-json-dev-123456789/US/CA/2021/intermediate/extraction/pipeline-US-CA-2021-test-001.json
```

### Intermediate File Formats

#### Extraction Output (`intermediate/extraction/{run_id}.json`)

Contains text blocks extracted from the PDF using Textract:

```json
{
  "blocks": [
    {
      "BlockType": "LINE",
      "Text": "Domain: Social-Emotional Development",
      "Confidence": 99.5,
      "Geometry": {...},
      "Page": 1
    }
  ],
  "total_pages": 70,
  "total_blocks": 19631,
  "extraction_timestamp": "2024-01-15T10:30:00Z",
  "source_s3_key": "US/CA/2021/california_standards.pdf",
  "source_version_id": "abc123"
}
```

#### Detection Output (`intermediate/detection/{run_id}.json`)

Contains detected structure elements with hierarchy levels:

```json
{
  "elements": [
    {
      "text": "Domain: Social-Emotional Development",
      "level": 1,
      "confidence": 0.95,
      "element_type": "domain"
    }
  ],
  "review_count": 5,
  "detection_timestamp": "2024-01-15T10:35:00Z",
  "source_extraction_key": "US/CA/2021/intermediate/extraction/pipeline-US-CA-2021-test-001.json"
}
```

#### Parsing Output (`intermediate/parsing/{run_id}.json`)

Contains parsed indicators with full hierarchy paths:

```json
{
  "indicators": [
    {
      "domain": "Social-Emotional Development",
      "strand": "Self-Regulation",
      "sub_strand": "Emotional Regulation",
      "code": "SE-1.1",
      "description": "Child demonstrates ability to manage emotions"
    }
  ],
  "total_indicators": 150,
  "parsing_timestamp": "2024-01-15T10:40:00Z",
  "source_detection_key": "US/CA/2021/intermediate/detection/pipeline-US-CA-2021-test-001.json"
}
```

#### Validation Summary (`intermediate/validation/{run_id}.json`)

Contains validation results and references to canonical records:

```json
{
  "validated_records": [
    "US/CA/2021/US-CA-2021-SE-1.1.json",
    "US/CA/2021/US-CA-2021-SE-1.2.json"
  ],
  "total_validated": 150,
  "validation_errors": [],
  "validation_timestamp": "2024-01-15T10:45:00Z",
  "source_parsing_key": "US/CA/2021/intermediate/parsing/pipeline-US-CA-2021-test-001.json"
}
```

### Verifying S3 Integration

#### 1. Check Intermediate Files After Pipeline Execution

After running a pipeline execution, verify all intermediate files were created:

```bash
# Set your bucket name and run_id
BUCKET="els-processed-json-dev-<account-id>"
RUN_ID="pipeline-US-CA-2021-test-001"

# List all intermediate files for a run
aws s3 ls s3://${BUCKET}/US/CA/2021/intermediate/ --recursive | grep ${RUN_ID}
```

Expected output:

```
2024-01-15 10:30:00  1234567  US/CA/2021/intermediate/extraction/pipeline-US-CA-2021-test-001.json
2024-01-15 10:35:00   234567  US/CA/2021/intermediate/detection/pipeline-US-CA-2021-test-001.json
2024-01-15 10:40:00   345678  US/CA/2021/intermediate/parsing/pipeline-US-CA-2021-test-001.json
2024-01-15 10:45:00    45678  US/CA/2021/intermediate/validation/pipeline-US-CA-2021-test-001.json
```

#### 2. Download and Inspect Intermediate Files

Download a specific intermediate file to inspect its contents:

```bash
# Download extraction output
aws s3 cp s3://${BUCKET}/US/CA/2021/intermediate/extraction/${RUN_ID}.json extraction_output.json

# View the file
cat extraction_output.json | jq '.'

# Check specific fields
cat extraction_output.json | jq '.total_blocks'
cat extraction_output.json | jq '.blocks[0]'
```

#### 3. Verify Data Flow Between Stages

Check that each stage references the previous stage's output:

```bash
# Download detection output
aws s3 cp s3://${BUCKET}/US/CA/2021/intermediate/detection/${RUN_ID}.json detection_output.json

# Verify it references extraction output
cat detection_output.json | jq '.source_extraction_key'

# Download parsing output
aws s3 cp s3://${BUCKET}/US/CA/2021/intermediate/parsing/${RUN_ID}.json parsing_output.json

# Verify it references detection output
cat parsing_output.json | jq '.source_detection_key'
```

#### 4. Verify Final Canonical Records

Check that canonical records were created:

```bash
# List canonical records
aws s3 ls s3://${BUCKET}/US/CA/2021/ | grep -v intermediate

# Download a canonical record
aws s3 cp s3://${BUCKET}/US/CA/2021/US-CA-2021-SE-1.1.json canonical_record.json

# Verify schema compliance
cat canonical_record.json | jq '.standard.standard_id'
```

#### 5. Check CloudWatch Logs for S3 Operations

Verify S3 operations in Lambda logs:

```bash
# Search for S3 save operations in extraction handler
aws logs filter-log-events \
  --log-group-name /aws/lambda/els-text-extractor-dev \
  --filter-pattern "Saved extraction output to S3" \
  --region us-east-1

# Search for S3 load operations in detection handler
aws logs filter-log-events \
  --log-group-name /aws/lambda/els-structure-detector-dev \
  --filter-pattern "Loaded" \
  --region us-east-1
```

### Troubleshooting S3 Integration Issues

#### Issue 1: Intermediate Files Not Created

**Symptoms**: Pipeline completes but intermediate files are missing in S3

**Diagnosis**:

```bash
# Check Lambda logs for S3 errors
aws logs tail /aws/lambda/els-text-extractor-dev --follow

# Look for errors like:
# - "Failed to save to S3"
# - "AccessDenied"
# - "NoSuchBucket"
```

**Solutions**:

1. Verify IAM permissions for Lambda roles:

```bash
# Check TextExtractor role has PutObject permission
aws iam get-role-policy \
  --role-name els-text-extractor-role-dev \
  --policy-name S3AccessPolicy
```

2. Verify bucket exists and is accessible:

```bash
aws s3 ls s3://els-processed-json-dev-<account-id>/
```

3. Check CloudFormation stack for IAM policy updates:

```bash
aws cloudformation describe-stack-resources \
  --stack-name els-pipeline-dev \
  --logical-resource-id TextExtractorRole
```

#### Issue 2: "Failed to load extraction output from S3"

**Symptoms**: Detection stage fails with error message about loading extraction output

**Diagnosis**:

```bash
# Check if extraction output exists
aws s3 ls s3://${BUCKET}/US/CA/2021/intermediate/extraction/${RUN_ID}.json

# Check detection handler logs
aws logs tail /aws/lambda/els-structure-detector-dev --follow
```

**Solutions**:

1. Verify extraction stage completed successfully:

```bash
# Check Step Functions execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> \
  --query 'events[?type==`TaskSucceeded` && contains(to_string(taskSucceededEventDetails), `text_extraction`)]'
```

2. Verify the output_artifact field contains correct S3 key:

```bash
# Check extraction handler output
aws logs filter-log-events \
  --log-group-name /aws/lambda/els-text-extractor-dev \
  --filter-pattern "output_artifact"
```

3. Verify StructureDetector role has GetObject permission:

```bash
aws iam get-role-policy \
  --role-name els-structure-detector-role-dev \
  --policy-name S3AccessPolicy
```

#### Issue 3: "No text blocks provided" Error

**Symptoms**: Detection stage fails with "No text blocks provided" even though extraction succeeded

**Diagnosis**:

```bash
# Download extraction output and check blocks array
aws s3 cp s3://${BUCKET}/US/CA/2021/intermediate/extraction/${RUN_ID}.json - | jq '.blocks | length'
```

**Solutions**:

1. If blocks array is empty, check extraction logic:

```bash
# Review extraction handler logs
aws logs tail /aws/lambda/els-text-extractor-dev --since 1h
```

2. If blocks exist but detection doesn't load them, check detection handler:

```bash
# Verify detection handler loads blocks correctly
aws logs filter-log-events \
  --log-group-name /aws/lambda/els-structure-detector-dev \
  --filter-pattern "Loaded" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

#### Issue 4: AccessDenied Errors

**Symptoms**: Lambda functions fail with S3 AccessDenied errors

**Diagnosis**:

```bash
# Check CloudWatch logs for AccessDenied
aws logs filter-log-events \
  --log-group-name /aws/lambda/els-text-extractor-dev \
  --filter-pattern "AccessDenied"
```

**Solutions**:

1. Update IAM policies in CloudFormation template:

```yaml
# Ensure Lambda roles have correct S3 permissions
- Effect: Allow
  Action:
    - s3:PutObject
  Resource: !Sub "${ProcessedJsonBucket.Arn}/*/intermediate/extraction/*"
```

2. Redeploy CloudFormation stack:

```bash
./scripts/deploy.sh -e dev -r us-east-1
```

3. Verify updated permissions:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::<account-id>:role/els-text-extractor-role-dev \
  --action-names s3:PutObject \
  --resource-arns arn:aws:s3:::els-processed-json-dev-<account-id>/US/CA/2021/intermediate/extraction/test.json
```

#### Issue 5: Large Intermediate Files

**Symptoms**: S3 operations are slow or Lambda functions timeout

**Diagnosis**:

```bash
# Check file sizes
aws s3 ls s3://${BUCKET}/US/CA/2021/intermediate/ --recursive --human-readable
```

**Solutions**:

1. For very large documents (>1000 pages), consider:
   - Increasing Lambda memory allocation (more memory = more CPU)
   - Implementing pagination for large block arrays
   - Using S3 multipart upload for files >5MB

2. Monitor Lambda execution time:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=els-text-extractor-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

### S3 Lifecycle Management

To manage storage costs, consider implementing lifecycle policies for intermediate data:

```bash
# Create lifecycle policy to delete intermediate files after 7 days
cat > lifecycle-policy.json <<EOF
{
  "Rules": [
    {
      "Id": "DeleteIntermediateFilesAfter7Days",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "intermediate/"
      },
      "Expiration": {
        "Days": 7
      }
    }
  ]
}
EOF

# Apply lifecycle policy
aws s3api put-bucket-lifecycle-configuration \
  --bucket els-processed-json-dev-<account-id> \
  --lifecycle-configuration file://lifecycle-policy.json
```

### Best Practices

1. **Always check intermediate files after pipeline failures** - They help identify which stage failed and why
2. **Use run_id consistently** - Ensures all intermediate files for a run can be easily found
3. **Monitor S3 costs** - Intermediate files can accumulate; implement lifecycle policies
4. **Keep intermediate files for debugging** - Don't delete immediately; useful for troubleshooting
5. **Use S3 versioning** - Already enabled on buckets; helps recover from accidental deletions
6. **Tag intermediate files** - Consider adding tags for easier cost tracking and management

---

## Monitoring and Logging

### CloudWatch Logs

View Lambda function logs:

```bash
# List log groups
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/els- \
  --region us-east-1

# Tail logs for ingester Lambda
aws logs tail /aws/lambda/els-ingester-dev \
  --follow \
  --region us-east-1
```

View Step Functions logs:

```bash
aws logs tail /aws/vendedlogs/states/els-pipeline-dev \
  --follow \
  --region us-east-1
```

### CloudWatch Metrics

Monitor key metrics:

- Lambda invocations, errors, duration
- Step Functions execution count, success/failure rate
- S3 bucket size and object count
- Aurora PostgreSQL connections, CPU, memory

Create CloudWatch dashboard:

```bash
# Use AWS Console to create a dashboard with:
# - Lambda error rates
# - Step Functions execution status
# - S3 bucket metrics
# - Aurora PostgreSQL metrics
```

### X-Ray Tracing

Enable X-Ray tracing for Lambda functions to trace requests through the pipeline:

```bash
# Update Lambda function configuration
aws lambda update-function-configuration \
  --function-name els-ingester-dev \
  --tracing-config Mode=Active \
  --region us-east-1
```

---

## Troubleshooting

### Common Issues

> **Note**: For S3 integration-specific issues, see the [S3 Intermediate Data Storage](#s3-intermediate-data-storage) section above.

#### Issue 1: CloudFormation Stack Creation Fails

**Symptoms**: Stack creation fails with IAM permission errors

**Solution**:

```bash
# Ensure you have CAPABILITY_NAMED_IAM capability
aws cloudformation create-stack \
  --stack-name els-pipeline-dev \
  --template-body file://infra/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

#### Issue 2: Lambda Function Timeout

**Symptoms**: Lambda functions timeout during execution

**Solution**:

- Increase Lambda timeout in CloudFormation template (default: 300 seconds for text extraction)
- Check Lambda memory allocation (increase if needed)
- Review CloudWatch logs for specific errors

#### Issue 3: Bedrock Access Denied

**Symptoms**: Lambda functions fail with Bedrock access denied errors

**Solution**:

```bash
# Verify Bedrock model access
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`) || contains(modelId, `titan`)].modelId'

# Request model access if needed (via Bedrock console)
```

#### Issue 4: Aurora PostgreSQL Connection Failures

**Symptoms**: Lambda functions cannot connect to Aurora

**Solution**:

- Verify Lambda functions are in the same VPC as Aurora
- Check security group rules allow PostgreSQL traffic (port 5432)
- Verify database credentials in Secrets Manager
- Check Aurora cluster status

```bash
# Test database connection from Lambda
aws lambda invoke \
  --function-name els-persistence-dev \
  --payload '{"test": "connection"}' \
  --region us-east-1 \
  response.json
```

#### Issue 5: S3 Path Structure Issues

**Symptoms**: Documents not found or incorrect path structure

**Solution**:

- Verify country code is uppercase 2-letter ISO 3166-1 alpha-2 format
- Ensure path follows pattern: `{country}/{state}/{year}/{filename}`
- Check S3 bucket permissions

```bash
# Verify path structure
aws s3 ls s3://els-raw-documents-dev-<account-id>/US/CA/2021/
```

#### Issue 6: Step Functions Execution Fails

**Symptoms**: Step Functions execution fails at specific stage

**Solution**:

```bash
# Get detailed execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> \
  --region us-east-1 \
  --output json > execution_history.json

# Review failed state details
cat execution_history.json | jq '.events[] | select(.type == "TaskFailed")'
```

### Debugging Tips

1. **Enable verbose logging**: Set Lambda environment variable `LOG_LEVEL=DEBUG`
2. **Use Step Functions console**: Visual representation of execution flow
3. **Check IAM roles**: Ensure Lambda execution roles have required permissions
4. **Review CloudWatch Insights**: Query logs across multiple Lambda functions
5. **Test individual stages**: Invoke Lambda functions directly with test payloads

---

## Cost Optimization

### Estimated Monthly Costs (Dev Environment)

- **S3**: $5-10 (storage + requests)
- **Lambda**: $10-20 (based on execution frequency)
- **Aurora Serverless v2**: $30-50 (0.5-2 ACUs)
- **Step Functions**: $5-10 (based on state transitions)
- **Textract**: Variable (pay per page)
- **Bedrock**: Variable (pay per token)
- **CloudWatch**: $5-10 (logs + metrics)

**Total**: ~$60-100/month for dev environment with moderate usage

### Cost Optimization Strategies

1. **Use Aurora Serverless v2 auto-scaling**: Set min capacity to 0.5 ACU
2. **Enable S3 Intelligent-Tiering**: Automatically move infrequently accessed objects to cheaper storage
3. **Set CloudWatch log retention**: Reduce retention period for non-critical logs
4. **Use Lambda reserved concurrency**: Prevent runaway costs from errors
5. **Implement S3 lifecycle policies**: Archive old documents to Glacier
6. **Monitor Bedrock token usage**: Optimize prompts to reduce token count
7. **Use Step Functions Express Workflows**: For high-volume, short-duration workflows

### Cost Monitoring

```bash
# Enable AWS Cost Explorer
# Set up budget alerts for the ELS pipeline

# Tag all resources with Project=ELS-Pipeline
# Use Cost Allocation Tags to track costs by project
```

---

## Next Steps

After successful deployment and testing:

1. **Set up CI/CD pipeline**: Automate deployments using GitHub Actions or AWS CodePipeline
2. **Implement monitoring dashboards**: Create CloudWatch dashboards for key metrics
3. **Configure alarms**: Set up CloudWatch alarms for errors and performance issues
4. **Document operational procedures**: Create runbooks for common operations
5. **Plan for production**: Review security, compliance, and disaster recovery requirements
6. **Scale testing**: Test with larger documents and higher volumes
7. **Integrate embeddings and recommendations**: Deploy tasks 15-18 for full pipeline

---

## Support and Resources

- **AWS Documentation**: https://docs.aws.amazon.com/
- **Bedrock Documentation**: https://docs.aws.amazon.com/bedrock/
- **Step Functions Documentation**: https://docs.aws.amazon.com/step-functions/
- **Aurora PostgreSQL Documentation**: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/

For issues or questions, contact the development team or create an issue in the repository.
