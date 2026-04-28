# Deployment Guide

How to deploy the ELS Pipeline and its web applications to AWS.

The project consists of four independent CDK stacks:

| Stack                | Script                   | What It Deploys                                                                             |
| -------------------- | ------------------------ | ------------------------------------------------------------------------------------------- |
| `els-pipeline-{env}` | `deploy_els_pipeline.sh` | S3 buckets, Lambda functions, Step Functions, Aurora PostgreSQL, Textract/Bedrock IAM roles |
| `els-app-{env}`      | `deploy_els_app.sh`      | Standards Explorer API (Lambda + API Gateway), frontend (S3 + CloudFront)                   |
| `els-planning-{env}` | `deploy_planning_app.sh` | Planning API (Lambda + API Gateway), Bedrock AgentCore Runtime, frontend (S3 + CloudFront)  |
| `els-landing-{env}`  | `deploy_landing_site.sh` | Landing site frontend (S3 + CloudFront)                                                     |

The app and planning stacks depend on the pipeline stack (they import its Aurora cluster and S3 bucket outputs).

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Python 3.13+
- Node.js 20+ and pnpm 9+
- Docker (CDK uses Docker to bundle Python Lambda code)
- IAM permissions for: CloudFormation, S3, Lambda, Step Functions, Aurora, Textract, Bedrock, CloudWatch, SNS, Secrets Manager, IAM, VPC, CloudFront, API Gateway, ACM, Route53

### Bedrock Model Access

Request access in the AWS Console under Bedrock → Model access for:

- `us.anthropic.claude-opus-4-7` (structure detection)
- `us.anthropic.claude-sonnet-4-6` (parsing, recommendations, planning agent)
- `amazon.titan-embed-text-v2:0` (embeddings)

## Pipeline Deployment

```bash
# Dev (default)
./scripts/deploy_els_pipeline.sh

# Production in a specific region
./scripts/deploy_els_pipeline.sh -e prod -r us-west-2
```

Options:

| Flag                  | Description                 | Default     |
| --------------------- | --------------------------- | ----------- |
| `-e`, `--environment` | `dev`, `staging`, or `prod` | `dev`       |
| `-r`, `--region`      | AWS region                  | `us-east-1` |

CDK handles Lambda code bundling automatically via Docker. When your Python source changes, CDK detects it and deploys new code. Initial deployment takes ~10-15 minutes (Aurora cluster creation).

## Standards Explorer App Deployment

```bash
# Full deploy to dev
DESCOPE_PROJECT_ID=<your-id> ./scripts/deploy_els_app.sh

# Deploy to production with custom domain
DESCOPE_PROJECT_ID=<your-id> ./scripts/deploy_els_app.sh \
  -e prod -d app.example.com --hosted-zone-id Z1234

# Redeploy code only (skip CDK)
./scripts/deploy_els_app.sh --skip-infra

# Frontend only
./scripts/deploy_els_app.sh --skip-infra --skip-api

# API only
./scripts/deploy_els_app.sh --skip-infra --skip-frontend
```

Options:

| Flag                  | Description                                  | Default     |
| --------------------- | -------------------------------------------- | ----------- |
| `-e`, `--environment` | `dev`, `staging`, or `prod`                  | `dev`       |
| `-r`, `--region`      | AWS region                                   | `us-east-1` |
| `--skip-infra`        | Skip CDK stack deployment                    | —           |
| `--skip-frontend`     | Skip frontend build and S3/CloudFront deploy | —           |
| `--skip-api`          | Skip API Lambda deploy                       | —           |
| `-d`, `--domain`      | Custom domain name                           | —           |
| `--hosted-zone-id`    | Route53 Hosted Zone ID for custom domain     | —           |

Requires `DESCOPE_PROJECT_ID` environment variable for authentication.

The script:

1. Deploys the CDK stack (API Gateway, Lambda, S3, CloudFront)
2. CDK bundles and deploys the API Lambda automatically
3. Builds `@els/shared` and `@els/frontend`, syncs to S3, invalidates CloudFront

## Planning App Deployment

```bash
# Full deploy to dev
DESCOPE_PROJECT_ID=<your-id> ./scripts/deploy_planning_app.sh

# Production with custom domain
DESCOPE_PROJECT_ID=<your-id> ./scripts/deploy_planning_app.sh \
  -e prod -d plan.example.com --hosted-zone-id Z1234

# Redeploy code only
./scripts/deploy_planning_app.sh --skip-infra

# Frontend only
./scripts/deploy_planning_app.sh --skip-infra --skip-api
```

Options are the same as the app deployment, plus:

| Flag              | Description                                 | Default          |
| ----------------- | ------------------------------------------- | ---------------- |
| `--bedrock-model` | Override the Bedrock model ID for the agent | template default |

This stack also deploys a Bedrock AgentCore Runtime that hosts the Strands-based planning agent (`packages/agentcore-agent/`).

## Landing Site Deployment

```bash
# Full deploy
./scripts/deploy_landing_site.sh

# Production with custom domain
./scripts/deploy_landing_site.sh -e prod -d example.com --hosted-zone-id Z1234

# Redeploy frontend only
./scripts/deploy_landing_site.sh --skip-infra
```

## GitHub Secrets (CI/CD)

If using GitHub Actions, configure these in `Settings > Secrets and variables > Actions`:

| Secret                  | Description                                     |
| ----------------------- | ----------------------------------------------- |
| `AWS_ACCESS_KEY_ID`     | IAM access key with deployment permissions      |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key                                  |
| `AWS_REGION`            | Target region (e.g. `us-east-1`)                |
| `ENVIRONMENT_NAME`      | Target environment: `dev`, `staging`, or `prod` |
| `DESCOPE_PROJECT_ID`    | Descope project ID for authentication           |
| `CUSTOM_DOMAIN`         | (prod only) Custom domain name                  |
| `HOSTED_ZONE_ID`        | (prod only) Route53 Hosted Zone ID              |

## Post-Deployment Verification

```bash
# Pipeline stack outputs
aws cloudformation describe-stacks --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs' --output table

# Check S3 buckets
aws s3 ls | grep els-

# Check Aurora cluster
aws rds describe-db-clusters --db-cluster-identifier els-database-cluster-dev \
  --query 'DBClusters[0].Status'

# Check Lambda functions
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `els-`)].FunctionName'

# Test upload
aws s3 cp standards/california_all_standards_2021.pdf \
  s3://${ELS_RAW_BUCKET}/US/CA/2021/california_all_standards_2021.pdf
```

## Environment Configuration

| Environment | Pipeline Stack         | App Stack         | Planning Stack         | Landing Stack         |
| ----------- | ---------------------- | ----------------- | ---------------------- | --------------------- |
| Development | `els-pipeline-dev`     | `els-app-dev`     | `els-planning-dev`     | `els-landing-dev`     |
| Staging     | `els-pipeline-staging` | `els-app-staging` | `els-planning-staging` | `els-landing-staging` |
| Production  | `els-pipeline-prod`    | `els-app-prod`    | `els-planning-prod`    | `els-landing-prod`    |

## Rollback

CDK/CloudFormation rolls back automatically on failure. To manually delete a stack:

```bash
aws cloudformation delete-stack --stack-name els-pipeline-dev
aws cloudformation wait stack-delete-complete --stack-name els-pipeline-dev
```

> Deleting the pipeline stack removes S3 buckets and their contents. Back up data first.

## Security

- All S3 buckets use AES256 encryption and block public access
- IAM roles follow least privilege (each Lambda has a dedicated role)
- S3 versioning enabled for audit trail
- Database credentials stored in Secrets Manager
- API authentication via Descope JWTs
- AgentCore agent validates Descope tokens and binds user_id per session

## Troubleshooting

| Issue                                       | Solution                                                             |
| ------------------------------------------- | -------------------------------------------------------------------- |
| Stack creation fails with permission errors | Ensure `CAPABILITY_NAMED_IAM` is set. Check IAM permissions.         |
| CDK bootstrap required                      | Run `npx cdk bootstrap aws://<account>/<region>` in `infra/cdk/`     |
| Docker not running                          | CDK needs Docker to bundle Python Lambda code. Start Docker Desktop. |
| `DESCOPE_PROJECT_ID` not set                | Export it before running app/planning deploy scripts                 |
| Aurora connection failure                   | Check VPC/security groups. Ensure Lambda is in same VPC.             |
| Bedrock access denied                       | Request model access in Bedrock console.                             |
| Frontend shows stale content                | CloudFront invalidation may take a few minutes to propagate.         |
