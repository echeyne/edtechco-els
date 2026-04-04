# AWS Operations Guide

Step-by-step instructions for operating the ELS Normalization Pipeline on AWS after deployment.

## Pre-Deployment Checklist

- AWS CLI v2 installed and configured
- Python 3.13+, Node.js 20+, pnpm 9+, Docker
- IAM permissions for: S3, Lambda, Step Functions, Aurora PostgreSQL, Textract, Bedrock, CloudWatch, SNS, Secrets Manager, IAM, VPC
- Bedrock model access enabled for Claude and Titan Embed models
- CDK bootstrapped: `npx cdk bootstrap aws://<account>/<region>` (run once per account/region)

To request Bedrock model access: AWS Console → Bedrock → Model access → Request access.

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
# Check status
aws stepfunctions describe-execution --execution-arn <ARN> --query 'status'

# Full execution history
aws stepfunctions get-execution-history --execution-arn <ARN> --max-results 100
```

You can also use the Step Functions console for a visual execution flow.

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

## Adding Documents from New States

Upload documents using the country-based path structure. The pipeline handles the country code automatically in all stages.

```bash
# Texas document
aws s3 cp texas_standards.pdf s3://${ELS_RAW_BUCKET}/US/TX/2022/texas_standards.pdf

# Arizona document
aws s3 cp arizona_standards.pdf s3://${ELS_RAW_BUCKET}/US/AZ/2018/arizona_standards.pdf
```

Then start a pipeline execution with the matching country/state/year in the input.

## Monitoring

```bash
# Lambda logs (follow mode)
aws logs tail /aws/lambda/els-ingester-dev --follow

# Step Functions logs
aws logs tail /aws/vendedlogs/states/els-pipeline-dev --follow
```

Key CloudWatch metrics to watch:

- Lambda: invocations, errors, duration, concurrent executions
- Step Functions: execution success/failure, execution time
- Aurora: connections, CPU utilization, ACU usage
- S3: bucket size, request count

## Database Operations

### Connecting to Aurora

Database credentials are stored in Secrets Manager. Retrieve them:

```bash
aws secretsmanager get-secret-value \
  --secret-id els-database-secret-dev \
  --query 'SecretString' --output text | jq '.'
```

### Running Migrations

See [infra/migrations/README.md](../infra/migrations/README.md) for the full migration guide. To run a new migration:

```bash
psql -h <aurora-endpoint> -U postgres -d els_corpus -f infra/migrations/009_alter_indicator_required_desc.sql
```

## Troubleshooting

| Issue                      | Diagnosis                                              | Fix                                                         |
| -------------------------- | ------------------------------------------------------ | ----------------------------------------------------------- |
| CloudFormation/CDK fails   | Check stack events in console                          | Ensure CDK is bootstrapped. Check IAM permissions.          |
| Lambda timeout             | Check CloudWatch logs                                  | Increase timeout/memory. Lower batch size config.           |
| Batch processing slow      | Check `MAX_CHUNKS_PER_BATCH` / `MAX_DOMAINS_PER_BATCH` | Lower batch size to reduce per-Lambda work.                 |
| Bedrock access denied      | `aws bedrock list-foundation-models`                   | Request model access in Bedrock console.                    |
| Aurora connection failure  | Check VPC/security groups                              | Ensure Lambda is in same VPC. Check port 5432 rules.        |
| S3 path issues             | `aws s3 ls s3://${BUCKET}/`                            | Verify country code is uppercase 2-letter ISO format.       |
| Intermediate files missing | Check Lambda logs for S3 errors                        | Verify IAM role has `s3:PutObject` on the processed bucket. |
| "No text blocks provided"  | Download extraction output, check `blocks` array       | Review extraction Lambda logs.                              |
| AgentCore connection fails | Check Planning API logs                                | Verify AgentCore Runtime ARN and IAM permissions.           |
| Frontend 403 errors        | Check CloudFront distribution                          | Verify S3 bucket policy allows CloudFront OAI access.       |

### Debugging Tips

- Set `LOG_LEVEL=DEBUG` on Lambda environment variables for verbose logging
- Use the Step Functions console for visual execution flow
- Use CloudWatch Insights to query across multiple Lambda log groups:
  ```
  fields @timestamp, @message
  | filter @message like /ERROR/
  | sort @timestamp desc
  | limit 50
  ```
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
| CloudFront           | $5-10                    |
| CloudWatch           | $5-10                    |
| **Total**            | **~$70-120**             |

### Cost Optimization

- Aurora Serverless v2: set min capacity to 0.5 ACU for dev
- S3 Intelligent-Tiering for infrequently accessed objects
- Reduce CloudWatch log retention for non-critical logs (7-14 days for dev)
- Implement S3 lifecycle policies for intermediate data
- Optimize Bedrock prompts to reduce token usage
- Use `--skip-infra` flags on deploy scripts to avoid unnecessary CDK deployments
