# Deployment Guide

How to deploy the ELS Pipeline to AWS using GitHub Actions or the deployment script.

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Python 3.9+
- GitHub repository with Actions enabled (for CI/CD)

## S3 Path Structure

All buckets use a country-based path layout (ISO 3166-1 alpha-2 codes):

| Bucket         | Pattern                                                  | Example                                         |
| -------------- | -------------------------------------------------------- | ----------------------------------------------- |
| Raw documents  | `{country}/{state}/{year}/{filename}`                    | `US/CA/2021/california_standards.pdf`           |
| Processed JSON | `{country}/{state}/{year}/{standard_id}.json`            | `US/CA/2021/US-CA-2021-LLD-1.2.json`            |
| Embeddings     | `{country}/{state}/{year}/embeddings/{standard_id}.json` | `US/CA/2021/embeddings/US-CA-2021-LLD-1.2.json` |

## GitHub Secrets

Configure these in `Settings > Secrets and variables > Actions`:

| Secret                  | Description                                     |
| ----------------------- | ----------------------------------------------- |
| `AWS_ACCESS_KEY_ID`     | IAM access key with deployment permissions      |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key                                  |
| `AWS_REGION`            | Target region (e.g. `us-east-1`)                |
| `ENVIRONMENT_NAME`      | Target environment: `dev`, `staging`, or `prod` |

The IAM user needs permissions for CloudFormation, S3, Lambda, IAM, and SSM.

## Automated Deployment (CI/CD)

Pushes to `main` trigger the GitHub Actions workflow:

1. Runs all tests (unit, property, integration)
2. Packages Lambda functions and uploads to S3
3. Deploys CloudFormation stack to dev
4. Deploys to prod after dev succeeds

## Manual Deployment

### Using the Deploy Script (Recommended)

```bash
# Dev (default)
./scripts/deploy.sh

# Production
./scripts/deploy.sh -e prod -r us-east-2
```

The script validates the template, deploys the stack, creates an environment `.env` file, and verifies success. Expect ~10-15 minutes for initial deployment (Aurora cluster creation).

### Using AWS CLI Directly

```bash
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name els-pipeline-dev \
  --parameter-overrides EnvironmentName=dev Region=us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM
```

## Post-Deployment

1. Get stack outputs:

   ```bash
   aws cloudformation describe-stacks \
     --stack-name els-pipeline-dev \
     --query 'Stacks[0].Outputs'
   ```

2. Update `.env` with the deployed bucket names (the deploy script does this automatically).

3. Verify:

   ```bash
   # Check buckets exist
   aws s3 ls | grep els-

   # Test upload with country path
   aws s3 cp test.pdf s3://${ELS_RAW_BUCKET}/US/CA/2021/test.pdf
   ```

## Environment Configuration

| Environment | Stack Name             | `ENVIRONMENT_NAME` |
| ----------- | ---------------------- | ------------------ |
| Development | `els-pipeline-dev`     | `dev`              |
| Staging     | `els-pipeline-staging` | `staging`          |
| Production  | `els-pipeline-prod`    | `prod`             |

## Adding Documents from New Countries

Upload documents using the country-based path structure. The pipeline handles the country code automatically in all stages.

```bash
# Canadian document
aws s3 cp ontario_standards.pdf s3://${ELS_RAW_BUCKET}/CA/ON/2022/ontario_standards.pdf

# Australian document
aws s3 cp nsw_standards.pdf s3://${ELS_RAW_BUCKET}/AU/NSW/2023/nsw_early_years.pdf
```

## Rollback

CloudFormation rolls back automatically on failure. To manually rollback or delete:

```bash
aws cloudformation delete-stack --stack-name els-pipeline-dev
aws cloudformation wait stack-delete-complete --stack-name els-pipeline-dev
```

> Deleting the stack removes all S3 buckets and their contents. Back up data first.

## Troubleshooting

| Issue                                       | Solution                                                                                     |
| ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Stack creation fails with permission errors | Ensure `CAPABILITY_NAMED_IAM` is set. Check IAM permissions.                                 |
| Stack already exists                        | The workflow uses `--no-fail-on-empty-changeset` for updates. Delete and recreate if needed. |
| Tests fail in CI                            | Run `pytest tests/ -v` locally to reproduce.                                                 |

## Cost Estimates

Current infrastructure (approximate monthly):

- S3: ~$0.023/GB
- CloudFormation, IAM, SSM: Free
- Lambda: ~$0.20/1M requests + compute
- Textract: ~$1.50/1K pages
- Bedrock: Model-specific token pricing
- Aurora Serverless v2: ~$0.12/ACU-hour

## Security

- All S3 buckets use AES256 encryption and block public access
- IAM roles follow least privilege (each Lambda has a dedicated role)
- S3 versioning enabled for audit trail
- Database credentials stored in Secrets Manager
