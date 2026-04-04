# ELS Pipeline Infrastructure

This directory contains the AWS infrastructure configuration for the ELS Normalization Pipeline, defined using AWS CDK (TypeScript).

## CDK Stacks

| Stack                | File                            | Description                                                                                             |
| -------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `els-pipeline-{env}` | `cdk/lib/pipeline-stack.ts`     | Core pipeline: S3 buckets, Lambda functions, Step Functions state machine, Aurora PostgreSQL, IAM roles |
| `els-app-{env}`      | `cdk/lib/app-stack.ts`          | Standards Explorer: API Lambda, API Gateway, S3 + CloudFront for frontend                               |
| `els-planning-{env}` | `cdk/lib/planning-stack.ts`     | Planning App: API Lambda, API Gateway, Bedrock AgentCore Runtime, S3 + CloudFront for frontend          |
| `els-landing-{env}`  | `cdk/lib/landing-site-stack.ts` | Landing Site: S3 + CloudFront for static site                                                           |

The app and planning stacks depend on the pipeline stack (they import Aurora cluster and S3 bucket references).

### Entry Point

`cdk/bin/app.ts` — Instantiates all stacks. Supports selective deployment via the `targetStack` CDK context variable, so deploy scripts can target a single stack.

### Shared Constructs

`cdk/lib/constructs/` — Reusable CDK constructs shared across stacks.

## S3 Bucket Structure

The pipeline uses a country-based path structure:

### Raw Documents Bucket

```
{country}/{state}/{year}/{filename}
```

Examples:

- `US/CA/2021/california_preschool_standards.pdf`
- `US/TX/2022/texas_early_learning_guidelines.pdf`

### Processed JSON Bucket

```
{country}/{state}/{year}/{standard_id}.json
```

Examples:

- `US/CA/2021/US-CA-2021-LLD-1.2.json`

### Intermediate Data

```
{country}/{state}/{year}/intermediate/{stage}/{run_id}.json
```

Used for debugging pipeline runs. See [AWS Operations Guide](../documentation/AWS_OPERATIONS.md) for details.

## IAM Roles

Each Lambda function has a dedicated IAM role following least privilege:

| Role                      | Permissions                                                               |
| ------------------------- | ------------------------------------------------------------------------- |
| Ingester                  | S3 read/write to raw bucket                                               |
| Text Extractor            | S3 read from raw bucket, Textract invoke                                  |
| Detection Batch Preparer  | S3 read (extraction output), S3 write (detection batches)                 |
| Detection Batch Processor | S3 read (detection batches), S3 write (detection results), Bedrock invoke |
| Detection Merger          | S3 read (batches + results), S3 write (detection output)                  |
| Parse Batch Preparer      | S3 read (detection output), S3 write (parsing batches)                    |
| Parse Batch Processor     | S3 read (parsing batches), S3 write (parsing results), Bedrock invoke     |
| Parse Merger              | S3 read (batches + results), S3 write (parsing output)                    |
| Validator                 | S3 read/write to processed bucket                                         |
| Embedding Generator       | Bedrock invoke (Titan Embed)                                              |
| Recommendation Generator  | Bedrock invoke (Claude)                                                   |
| Persister                 | Aurora Data API, Secrets Manager                                          |

## Database

Aurora PostgreSQL Serverless v2 with pgvector extension. See [migrations/README.md](migrations/README.md) for schema details.

## Deployment

```bash
# From project root
./scripts/deploy_els_pipeline.sh -e dev
./scripts/deploy_els_app.sh -e dev
./scripts/deploy_planning_app.sh -e dev
./scripts/deploy_landing_site.sh -e dev
```

See [Deployment Guide](../documentation/DEPLOYMENT.md) for full details.

## CDK Development

```bash
cd infra/cdk
npm install

# Synthesize CloudFormation template
npx cdk synth els-pipeline-dev

# Preview changes
npx cdk diff els-pipeline-dev

# Deploy
npx cdk deploy els-pipeline-dev -c environment=dev
```
