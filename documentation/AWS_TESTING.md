# AWS Operations Guide

Step-by-step instructions for deploying, verifying, and operating the ELS Normalization Pipeline on AWS.

## Pre-Deployment Checklist

- AWS CLI v2 installed and configured
- Python 3.11+
- IAM permissions for: S3, Lambda, Step Functions, Aurora PostgreSQL, Textract, Bedrock, CloudWatch, SNS, Secrets Manager, IAM, VPC
- Bedrock model access enabled for `us.anthropic.claude-sonnet-4-6` and `amazon.titan-embed-text-v2:0`

To request Bedrock model access: AWS Console → Bedrock → Model access → Request access.

## Deployment

```bash
# 1. Install
python3 -m venv venv && source venv/bin/activate
pip install -e .

# 2. Configure
cp .env.example .env  # Edit with your values

# 3. Deploy
./scripts/deploy.sh                          # Dev (default)
./scripts/deploy.sh -e staging -r us-west-2  # Staging
./scripts/deploy.sh -e prod -r us-east-1     # Production
```

Deployment takes ~10-15 minutes (Aurora cluster creation). The script packages Lambdas, validates the template, deploys, and outputs resource names.

## Post-Deployment Verification

```bash
# Stack outputs
aws cloudformation describe-stacks --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs' --output table

# S3 buckets
aws s3 ls | grep els-

# Aurora cluster status
aws rds describe-db-clusters --db-cluster-identifier els-database-cluster-dev \
  --query 'DBClusters[0].Status'

# Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `els-`)].FunctionName'

# Step Functions state machine
aws stepfunctions describe-state-machine --state-machine-arn <ARN>
```

## Running the Pipeline

### Upload a Document

```bash
aws s3 cp standards/california_all_standards_2021.pdf \
  s3://${ELS_RAW_BUCKET}/US/CA/2021/california_all_standards_2021.pdf
```

### Start a Pipeline Execution

```bash
aws stepfunctions start-execution \
  --state-machine-arn <PipelineStateMachineArn> \
  --name "test-$(date +%s)" \
  --input '{
    "run_id": "pipeline-US-CA-2021-test-001",
    "file_path": "US/CA/2021/california_all_standards_2021.pdf",
    "country": "US", "state": "CA", "version_year": 2021,
    "filename": "california_all_standards_2021.pdf"
  }'
```

### Monitor Execution

```bash
aws stepfunctions describe-execution --execution-arn <ARN> --query 'status'
aws stepfunctions get-execution-history --execution-arn <ARN> --max-results 100
```

### Verify Outputs

```bash
# Intermediate files
aws s3 ls s3://${ELS_PROCESSED_BUCKET}/US/CA/2021/intermediate/ --recursive

# Final canonical records
aws s3 ls s3://${ELS_PROCESSED_BUCKET}/US/CA/2021/ | grep -v intermediate
```

## S3 Intermediate Data

Each pipeline stage writes intermediate output to S3 for debugging:

```
{country}/{state}/{year}/intermediate/
  ├── extraction/{run_id}.json          # Textract blocks
  ├── detection/manifest/{run_id}.json  # Detection batch manifest
  ├── detection/batch-N/{run_id}.json   # Per-batch text blocks
  ├── detection/result-N/{run_id}.json  # Per-batch detection results
  ├── detection/{run_id}.json           # Merged detection output
  ├── parsing/manifest/{run_id}.json    # Parse batch manifest
  ├── parsing/batch-N/{run_id}.json     # Per-batch elements
  ├── parsing/result-N/{run_id}.json    # Per-batch parse results
  ├── parsing/{run_id}.json             # Merged parsing output
  └── validation/{run_id}.json          # Validation summary
```

To inspect:

```bash
BUCKET="${ELS_PROCESSED_BUCKET}"
RUN_ID="pipeline-US-CA-2021-test-001"

# List all intermediate files for a run
aws s3 ls s3://${BUCKET}/US/CA/2021/intermediate/ --recursive | grep ${RUN_ID}

# Download and inspect
aws s3 cp s3://${BUCKET}/US/CA/2021/intermediate/extraction/${RUN_ID}.json - | jq '.'
```

### Lifecycle Management

To auto-delete intermediate files after 7 days:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket ${ELS_PROCESSED_BUCKET} \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "DeleteIntermediateAfter7Days",
      "Status": "Enabled",
      "Filter": {"Prefix": "intermediate/"},
      "Expiration": {"Days": 7}
    }]
  }'
```

## Monitoring

```bash
# Lambda logs
aws logs tail /aws/lambda/els-ingester-dev --follow

# Step Functions logs
aws logs tail /aws/vendedlogs/states/els-pipeline-dev --follow
```

Key CloudWatch metrics to watch: Lambda invocations/errors/duration, Step Functions execution success/failure, Aurora connections/CPU, S3 bucket size.

## Troubleshooting

| Issue                      | Diagnosis                                              | Fix                                                           |
| -------------------------- | ------------------------------------------------------ | ------------------------------------------------------------- |
| CloudFormation fails       | Check stack events                                     | Ensure `CAPABILITY_NAMED_IAM`. Verify IAM permissions.        |
| Lambda timeout             | Check CloudWatch logs                                  | Increase timeout/memory in template. Check batch size config. |
| Batch processing slow      | Check `MAX_CHUNKS_PER_BATCH` / `MAX_DOMAINS_PER_BATCH` | Lower batch size to reduce per-Lambda work.                   |
| Bedrock access denied      | `aws bedrock list-foundation-models`                   | Request model access in Bedrock console.                      |
| Aurora connection failure  | Check VPC/security groups                              | Ensure Lambda is in same VPC. Check port 5432 rules.          |
| S3 path issues             | `aws s3 ls s3://${BUCKET}/`                            | Verify country code is uppercase 2-letter ISO format.         |
| Intermediate files missing | Check Lambda logs for S3 errors                        | Verify IAM role has `s3:PutObject` on the processed bucket.   |
| "No text blocks provided"  | Download extraction output, check `blocks` array       | Review extraction Lambda logs.                                |

### Debugging Tips

- Set `LOG_LEVEL=DEBUG` on Lambda environment variables for verbose logging
- Use the Step Functions console for visual execution flow
- Use CloudWatch Insights to query across multiple Lambda log groups
- Test individual stages by invoking Lambdas directly with test payloads

## Cost Estimates (Dev Environment)

| Service              | Approximate Monthly Cost |
| -------------------- | ------------------------ |
| S3                   | $5-10                    |
| Lambda               | $10-20                   |
| Aurora Serverless v2 | $30-50 (0.5-2 ACUs)      |
| Step Functions       | $5-10                    |
| Textract             | Variable (per page)      |
| Bedrock              | Variable (per token)     |
| CloudWatch           | $5-10                    |
| **Total**            | **~$60-100**             |

### Cost Optimization

- Aurora Serverless v2: set min capacity to 0.5 ACU
- S3 Intelligent-Tiering for infrequently accessed objects
- Reduce CloudWatch log retention for non-critical logs
- Implement S3 lifecycle policies for intermediate data
- Optimize Bedrock prompts to reduce token usage
