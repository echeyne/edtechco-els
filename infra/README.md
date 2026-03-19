# ELS Pipeline Infrastructure

This directory contains the AWS infrastructure configuration for the ELS Normalization Pipeline.

## Overview

The ELS Pipeline infrastructure is defined using AWS CloudFormation and supports multi-country deployments with country-based path structures.

## Files

- `template.yaml` - Main CloudFormation template defining all AWS resources
- `migrations/` - Database migration scripts for Aurora PostgreSQL

## S3 Bucket Structure

The pipeline uses a country-based path structure to organize documents and data:

### Raw Documents Bucket

```
{country}/{state}/{year}/{filename}
```

**Examples:**

- `US/CA/2021/california_preschool_standards.pdf`
- `CA/ON/2022/ontario_early_learning_framework.pdf`
- `AU/NSW/2023/nsw_early_years_framework.pdf`

### Processed JSON Bucket

```
{country}/{state}/{year}/{standard_id}.json
```

**Examples:**

- `US/CA/2021/US-CA-2021-LLD-1.2.json`
- `CA/ON/2022/CA-ON-2022-COM-3.1.json`
- `AU/NSW/2023/AU-NSW-2023-PHY-2.4.json`

### Embeddings Bucket (when implemented)

```
{country}/{state}/{year}/embeddings/{standard_id}.json
```

**Examples:**

- `US/CA/2021/embeddings/US-CA-2021-LLD-1.2.json`

## Country Code Support

### ISO 3166-1 Alpha-2 Format

All country codes follow the ISO 3166-1 alpha-2 standard (two-letter codes):

| Country        | Code | Example State/Province |
| -------------- | ---- | ---------------------- |
| United States  | US   | CA, TX, NY             |
| Canada         | CA   | ON, BC, QC             |
| Australia      | AU   | NSW, VIC, QLD          |
| United Kingdom | GB   | ENG, SCT, WLS          |
| New Zealand    | NZ   | AKL, WGN, CAN          |

### Validation

Country codes are validated at multiple levels:

1. **Ingestion**: Validates country code format before storing documents
2. **Parser**: Includes country code in Standard_ID generation
3. **Validator**: Enforces country code presence in all records
4. **Database**: Country columns indexed for efficient querying

## Resources

### S3 Buckets

1. **RawDocumentsBucket**
   - Name: `els-raw-documents-{environment}-{account-id}`
   - Versioning: Enabled
   - Encryption: AES256
   - Purpose: Store original PDF/HTML documents

2. **ProcessedJsonBucket**
   - Name: `els-processed-json-{environment}-{account-id}`
   - Versioning: Enabled
   - Encryption: AES256
   - Purpose: Store validated Canonical_JSON records

3. **EmbeddingsBucket** (to be added)
   - Name: `els-embeddings-{environment}-{account-id}`
   - Versioning: Enabled
   - Encryption: AES256
   - Purpose: Store embedding records

### IAM Roles

1. **IngesterLambdaRole**
   - Permissions: S3 read/write to RawDocumentsBucket
   - Purpose: Upload and tag raw documents

2. **TextExtractorLambdaRole**
   - Permissions: S3 read from RawDocumentsBucket, Textract invoke
   - Purpose: Extract text from PDFs

3. **StructureDetectorLambdaRole**
   - Permissions: Bedrock invoke (Claude models)
   - Purpose: Detect document structure using LLM

4. **HierarchyParserLambdaRole**
   - Permissions: Basic Lambda execution
   - Purpose: Parse and normalize hierarchy

5. **ValidatorLambdaRole**
   - Permissions: S3 read/write to ProcessedJsonBucket
   - Purpose: Validate and store Canonical_JSON

6. **DetectionBatchPreparerRole**
   - Permissions: S3 read (extraction output), S3 write (detection batches)
   - Purpose: Split text blocks into bounded detection batches

7. **DetectionBatchProcessorRole**
   - Permissions: S3 read (detection batches), S3 write (detection results), Bedrock invoke
   - Purpose: Process a single detection batch through Bedrock

8. **DetectionMergerRole**
   - Permissions: S3 read (detection batches + results), S3 write (detection output)
   - Purpose: Merge and deduplicate detection batch results

9. **ParseBatchPreparerRole**
   - Permissions: S3 read (detection output), S3 write (parsing batches)
   - Purpose: Split detected elements into bounded parse batches by domain

10. **ParseBatchProcessorRole**
    - Permissions: S3 read (parsing batches), S3 write (parsing results), Bedrock invoke
    - Purpose: Process a single parse batch through Bedrock

11. **ParseMergerRole**
    - Permissions: S3 read (parsing batches + results), S3 write (parsing output)
    - Purpose: Merge parse batch results into final output

### Lambda Functions (to be added)

Lambda functions will be added in subsequent tasks with the following environment variables:

```yaml
Environment:
  Variables:
    ELS_RAW_BUCKET: !Ref RawDocumentsBucket
    ELS_PROCESSED_BUCKET: !Ref ProcessedJsonBucket
    ELS_EMBEDDINGS_BUCKET: !Ref EmbeddingsBucket
    ENVIRONMENT: !Ref EnvironmentName
    AWS_REGION: !Ref AWS::Region
    COUNTRY_CODE_VALIDATION: "enabled"
    S3_PATH_PATTERN: "{country}/{state}/{year}/{identifier}"
```

#### Batching Lambda Functions

| Function                              | Handler                                                   | Timeout | Memory | Purpose                                     |
| ------------------------------------- | --------------------------------------------------------- | ------- | ------ | ------------------------------------------- |
| `els-prepare-detection-batches-{env}` | `els_pipeline.handlers.prepare_detection_batches_handler` | 60s     | 512MB  | Split text blocks into detection batches    |
| `els-detect-batch-{env}`              | `els_pipeline.handlers.detect_batch_handler`              | 600s    | 1024MB | Process one detection batch via Bedrock     |
| `els-merge-detection-results-{env}`   | `els_pipeline.handlers.merge_detection_results_handler`   | 120s    | 512MB  | Merge and deduplicate detection results     |
| `els-prepare-parse-batches-{env}`     | `els_pipeline.handlers.prepare_parse_batches_handler`     | 60s     | 512MB  | Split elements into parse batches by domain |
| `els-parse-batch-{env}`               | `els_pipeline.handlers.parse_batch_handler`               | 600s    | 1024MB | Process one parse batch via Bedrock         |
| `els-merge-parse-results-{env}`       | `els_pipeline.handlers.merge_parse_results_handler`       | 120s    | 512MB  | Merge parse results into final output       |

Batch processor Lambdas include additional env vars: `MAX_CHUNKS_PER_BATCH`, `MAX_DOMAINS_PER_BATCH`, `BEDROCK_DETECTOR_LLM_MODEL_ID`, `CONFIDENCE_THRESHOLD`.

### Step Functions (to be added)

AWS Step Functions state machine will orchestrate the pipeline stages:

1. Ingestion
2. Text Extraction
3. Detection Batching (Prepare → Map: Detect Batch ×N, MaxConcurrency 3 → Merge)
4. Parse Batching (Prepare → Map: Parse Batch ×N, MaxConcurrency 3 → Merge)
5. Validation
6. Embedding Generation
7. Recommendation Generation
8. Data Persistence

The detection and parsing stages use an iterative batching pattern with Step Functions Map states for parallel execution. Batch sizes are controlled by `MAX_CHUNKS_PER_BATCH` (default 5) and `MAX_DOMAINS_PER_BATCH` (default 3) environment variables.

### Aurora PostgreSQL (to be added)

Aurora Serverless PostgreSQL cluster with pgvector extension:

- Database: `els_pipeline`
- Extension: `pgvector` for embedding storage
- Tables: documents, domains, strands, sub_strands, indicators, embeddings, recommendations
- All tables include `country` column for multi-country support

## Deployment

### Using the Deployment Script (Recommended)

```bash
# Deploy to dev
./scripts/deploy.sh

# Deploy to staging
./scripts/deploy.sh -e staging -r us-west-2

# Deploy to production
./scripts/deploy.sh -e prod
```

### Using AWS CLI

```bash
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name els-pipeline-dev \
  --parameter-overrides \
    EnvironmentName=dev \
    Region=us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM
```

### Validation

Validate the template before deployment:

```bash
aws cloudformation validate-template \
  --template-body file://infra/template.yaml
```

## Stack Outputs

After deployment, the stack provides these outputs:

- `RawDocumentsBucketName` - Name of the raw documents bucket
- `RawDocumentsBucketArn` - ARN of the raw documents bucket
- `ProcessedJsonBucketName` - Name of the processed JSON bucket
- `ProcessedJsonBucketArn` - ARN of the processed JSON bucket
- `IngesterLambdaRoleArn` - ARN of the ingester Lambda role
- `TextExtractorLambdaRoleArn` - ARN of the text extractor Lambda role
- `StructureDetectorLambdaRoleArn` - ARN of the structure detector Lambda role
- `HierarchyParserLambdaRoleArn` - ARN of the hierarchy parser Lambda role
- `ValidatorLambdaRoleArn` - ARN of the validator Lambda role

## Environment Variables

After deployment, configure these environment variables:

```bash
# Get bucket names from stack outputs
export ELS_RAW_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
  --output text)

export ELS_PROCESSED_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ProcessedJsonBucketName`].OutputValue' \
  --output text)

# Set other variables
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
export COUNTRY_CODE_VALIDATION=enabled
export S3_PATH_PATTERN="{country}/{state}/{year}/{identifier}"
```

## Testing

### Verify S3 Buckets

```bash
# List buckets
aws s3 ls | grep els-

# Test country-based path structure
echo "test" > test.pdf
aws s3 cp test.pdf s3://${ELS_RAW_BUCKET}/US/CA/2021/test.pdf
aws s3 ls s3://${ELS_RAW_BUCKET}/US/CA/2021/
```

### Verify IAM Roles

```bash
# Check ingester role
aws iam get-role --role-name els-ingester-lambda-role-dev

# List all ELS roles
aws iam list-roles --query 'Roles[?contains(RoleName, `els-`)].RoleName'
```

## Monitoring

### CloudFormation Events

```bash
# Watch stack events during deployment
aws cloudformation describe-stack-events \
  --stack-name els-pipeline-dev \
  --max-items 20
```

### S3 Metrics

```bash
# Get bucket size
aws s3 ls s3://${ELS_RAW_BUCKET} --recursive --summarize

# List objects by country
aws s3 ls s3://${ELS_RAW_BUCKET}/US/ --recursive
aws s3 ls s3://${ELS_RAW_BUCKET}/CA/ --recursive
```

## Cost Estimation

Current infrastructure costs (approximate):

| Resource       | Cost             | Notes               |
| -------------- | ---------------- | ------------------- |
| S3 Storage     | $0.023/GB/month  | Standard storage    |
| S3 Requests    | $0.0004/1000 PUT | Upload costs        |
| CloudFormation | Free             | No charge           |
| IAM            | Free             | No charge           |
| SSM Parameters | Free             | Standard parameters |

Future additions:

- Lambda: $0.20 per 1M requests + compute time
- Textract: $1.50 per 1000 pages
- Bedrock: Model-specific pricing
- Aurora Serverless: $0.12/ACU-hour

## Security

### Encryption

- All S3 buckets use AES256 encryption at rest
- Data in transit uses TLS 1.2+

### Access Control

- S3 buckets block all public access
- IAM roles follow least privilege principle
- Each Lambda has dedicated role with minimal permissions

### Compliance

- S3 versioning enabled for audit trail
- CloudTrail recommended for API logging
- VPC recommended for Aurora (to be added)

## Troubleshooting

### Stack Creation Fails

```bash
# Check stack events
aws cloudformation describe-stack-events \
  --stack-name els-pipeline-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'

# Delete failed stack
aws cloudformation delete-stack --stack-name els-pipeline-dev
```

### Bucket Already Exists

If bucket names conflict:

1. Delete the existing stack
2. Wait for buckets to be deleted
3. Redeploy

### Permission Errors

Ensure your IAM user/role has these permissions:

- `cloudformation:*`
- `s3:*`
- `iam:*`
- `ssm:*`

## Maintenance

### Updating the Stack

```bash
# Update with new template
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name els-pipeline-dev \
  --parameter-overrides EnvironmentName=dev \
  --capabilities CAPABILITY_NAMED_IAM
```

### Deleting the Stack

```bash
# Delete stack (will delete all resources)
aws cloudformation delete-stack --stack-name els-pipeline-dev

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name els-pipeline-dev
```

**Warning:** Deleting the stack will delete all S3 buckets and their contents. Ensure you have backups if needed.

## Multi-Country Deployment Example

### Adding Canadian Standards

```bash
# Upload Canadian document
aws s3 cp ontario_standards.pdf \
  s3://${ELS_RAW_BUCKET}/CA/ON/2022/ontario_early_learning.pdf

# Verify upload
aws s3 ls s3://${ELS_RAW_BUCKET}/CA/ON/2022/

# After processing, check output
aws s3 ls s3://${ELS_PROCESSED_BUCKET}/CA/ON/2022/
```

### Adding Australian Standards

```bash
# Upload Australian document
aws s3 cp nsw_standards.pdf \
  s3://${ELS_RAW_BUCKET}/AU/NSW/2023/nsw_early_years.pdf

# Verify upload
aws s3 ls s3://${ELS_RAW_BUCKET}/AU/NSW/2023/

# After processing, check output
aws s3 ls s3://${ELS_PROCESSED_BUCKET}/AU/NSW/2023/
```

## References

- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [AWS S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/best-practices.html)
- [ISO 3166-1 Country Codes](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
- [ELS Pipeline Design Document](../.kiro/specs/els-normalization-pipeline/design.md)
