#!/bin/bash

# ELS Planning App Deployment Script
# Deploys the planning tool: CloudFormation infra, API Lambda, Action Group Lambda,
# frontend (S3 + CloudFront), and Bedrock Agent resources.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-planning-${ENVIRONMENT}"
TEMPLATE_FILE="infra/planning-template.yaml"
SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_message() {
    echo -e "${1}${2}${NC}"
}

print_header() {
    echo ""
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "$1"
    print_message "$BLUE" "=========================================="
    echo ""
}

# ─── Parse arguments ───
SKIP_INFRA=false
SKIP_FRONTEND=false
SKIP_API=false
SKIP_ACTION_GROUP=false
CUSTOM_DOMAIN=""
HOSTED_ZONE_ID=""
BEDROCK_MODEL_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            STACK_NAME="els-planning-${ENVIRONMENT}"
            shift 2 ;;
        -r|--region)
            REGION="$2"
            shift 2 ;;
        --skip-infra)
            SKIP_INFRA=true
            shift ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift ;;
        --skip-api)
            SKIP_API=true
            shift ;;
        --skip-action-group)
            SKIP_ACTION_GROUP=true
            shift ;;
        -d|--domain)
            CUSTOM_DOMAIN="$2"
            shift 2 ;;
        --hosted-zone-id)
            HOSTED_ZONE_ID="$2"
            shift 2 ;;
        --bedrock-model)
            BEDROCK_MODEL_ID="$2"
            shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV       Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION         AWS region [default: us-east-1]"
            echo "  --skip-infra                Skip CloudFormation deployment"
            echo "  --skip-frontend             Skip frontend build & deploy"
            echo "  --skip-api                  Skip Planning API Lambda deploy"
            echo "  --skip-action-group         Skip Action Group Lambda deploy"
            echo "  -d, --domain DOMAIN         Custom domain (e.g. plan.example.com)"
            echo "  --hosted-zone-id ID         Route53 Hosted Zone ID for custom domain"
            echo "  --bedrock-model MODEL_ID    Bedrock model ID [default: template default]"
            echo "  -h, --help                  Show this help"
            echo ""
            echo "Environment Variables:"
            echo "  ENVIRONMENT                 Environment name (overridden by -e)"
            echo "  AWS_REGION                  AWS region (overridden by -r)"
            echo "  DESCOPE_PROJECT_ID          (required) Descope project ID for auth"
            echo ""
            echo "Examples:"
            echo "  $0                                          # Full deploy to dev"
            echo "  $0 -e prod -d plan.example.com --hosted-zone-id Z1234"
            echo "  $0 --skip-infra                             # Redeploy code only"
            echo "  $0 --skip-infra --skip-action-group         # API + frontend only"
            exit 0 ;;
        *)
            print_message "$RED" "Unknown option: $1"
            exit 1 ;;
    esac
done

# ─── Prerequisites ───
check_prerequisites() {
    print_header "Checking Prerequisites"

    for cmd in aws node pnpm; do
        if ! command -v $cmd &> /dev/null; then
            print_message "$RED" "❌ $cmd not found. Please install it."
            exit 1
        fi
    done
    print_message "$GREEN" "✓ Required tools found (aws, node, pnpm)"

    if ! aws sts get-caller-identity &> /dev/null; then
        print_message "$RED" "❌ AWS credentials not configured or invalid."
        exit 1
    fi
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_message "$GREEN" "✓ AWS credentials valid (account: $ACCOUNT_ID)"

    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_message "$RED" "❌ Template not found: $TEMPLATE_FILE"
        exit 1
    fi
    print_message "$GREEN" "✓ CloudFormation template found"
}

# ─── Helper: get stack output ───
get_output() {
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey==\`$1\`].OutputValue" \
        --output text
}

# ─── Deploy CloudFormation stack ───
deploy_infra() {
    print_header "Deploying Planning Infrastructure"

    PIPELINE_STACK="els-pipeline-${ENVIRONMENT}"
    print_message "$YELLOW" "Stack: $STACK_NAME | Env: $ENVIRONMENT | Region: $REGION"
    print_message "$YELLOW" "Pipeline stack (cross-ref): $PIPELINE_STACK"

    if [ -z "$DESCOPE_PROJECT_ID" ]; then
        print_message "$RED" "❌ DESCOPE_PROJECT_ID environment variable is required"
        exit 1
    fi

    PARAM_OVERRIDES="EnvironmentName=$ENVIRONMENT PipelineStackName=$PIPELINE_STACK DescopeProjectId=$DESCOPE_PROJECT_ID"

    if [ -n "$CUSTOM_DOMAIN" ]; then
        PARAM_OVERRIDES="$PARAM_OVERRIDES CustomDomainName=$CUSTOM_DOMAIN"
        print_message "$YELLOW" "Custom domain: $CUSTOM_DOMAIN"
    fi
    if [ -n "$HOSTED_ZONE_ID" ]; then
        PARAM_OVERRIDES="$PARAM_OVERRIDES HostedZoneId=$HOSTED_ZONE_ID"
    fi
    if [ -n "$BEDROCK_MODEL_ID" ]; then
        PARAM_OVERRIDES="$PARAM_OVERRIDES BedrockAgentModelId=$BEDROCK_MODEL_ID"
        print_message "$YELLOW" "Bedrock model: $BEDROCK_MODEL_ID"
    fi

    aws cloudformation deploy \
        --template-file "$TEMPLATE_FILE" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides $PARAM_OVERRIDES \
        --capabilities CAPABILITY_NAMED_IAM \
        --no-fail-on-empty-changeset \
        --region "$REGION"

    print_message "$GREEN" "✓ Infrastructure deployed"
}

# ─── Build & deploy Planning API Lambda ───
deploy_api() {
    print_header "Building & Deploying Planning API"

    LAMBDA_NAME=$(get_output PlanningApiLambdaFunctionName)
    print_message "$YELLOW" "Lambda: $LAMBDA_NAME"

    # Build shared + planning-api
    print_message "$BLUE" "Building packages..."
    pnpm --filter @els/shared run build
    pnpm --filter @els/planning-api run build

    # Bundle for Lambda with esbuild
    print_message "$BLUE" "Bundling for Lambda..."
    mkdir -p build/planning-api-lambda

    npx esbuild packages/planning-api/dist/lambda.js \
        --bundle \
        --platform=node \
        --target=node20 \
        --format=esm \
        --outfile=build/planning-api-lambda/index.mjs \
        --external:@aws-sdk/* \
        --banner:js="import { createRequire } from 'module'; const require = createRequire(import.meta.url);"

    # Package as zip
    print_message "$BLUE" "Packaging zip..."
    rm -f build/planning-api-lambda.zip
    (cd build/planning-api-lambda && zip -r ../planning-api-lambda.zip .)

    # Deploy
    print_message "$BLUE" "Updating Lambda function code..."
    aws lambda update-function-code \
        --function-name "$LAMBDA_NAME" \
        --zip-file fileb://build/planning-api-lambda.zip \
        --region "$REGION" > /dev/null

    aws lambda wait function-updated \
        --function-name "$LAMBDA_NAME" \
        --region "$REGION"

    print_message "$GREEN" "✓ Planning API deployed"
}

# ─── Build & deploy Action Group Lambda ───
deploy_action_group() {
    print_header "Building & Deploying Action Group Lambda"

    LAMBDA_NAME=$(get_output ActionGroupLambdaFunctionName)
    print_message "$YELLOW" "Lambda: $LAMBDA_NAME"

    # Shared + planning-api should already be built from deploy_api,
    # but build again if running standalone
    pnpm --filter @els/shared run build
    pnpm --filter @els/planning-api run build

    # Bundle the action group handler
    print_message "$BLUE" "Bundling for Lambda..."
    mkdir -p build/action-group-lambda

    npx esbuild packages/planning-api/dist/action-group/handler.js \
        --bundle \
        --platform=node \
        --target=node20 \
        --format=esm \
        --outfile=build/action-group-lambda/index.mjs \
        --external:@aws-sdk/* \
        --banner:js="import { createRequire } from 'module'; const require = createRequire(import.meta.url);"

    # Package as zip
    print_message "$BLUE" "Packaging zip..."
    rm -f build/action-group-lambda.zip
    (cd build/action-group-lambda && zip -r ../action-group-lambda.zip .)

    # Deploy
    print_message "$BLUE" "Updating Lambda function code..."
    aws lambda update-function-code \
        --function-name "$LAMBDA_NAME" \
        --zip-file fileb://build/action-group-lambda.zip \
        --region "$REGION" > /dev/null

    aws lambda wait function-updated \
        --function-name "$LAMBDA_NAME" \
        --region "$REGION"

    print_message "$GREEN" "✓ Action Group Lambda deployed"
}

# ─── Build & deploy frontend ───
deploy_frontend() {
    print_header "Building & Deploying Planning Frontend"

    CLOUDFRONT_DOMAIN=$(get_output PlanningCloudFrontDomainName)
    FRONTEND_BUCKET=$(get_output PlanningFrontendBucketName)
    DISTRIBUTION_ID=$(get_output PlanningCloudFrontDistributionId)

    print_message "$YELLOW" "Bucket: $FRONTEND_BUCKET"
    print_message "$YELLOW" "CloudFront: $CLOUDFRONT_DOMAIN"

    # Build
    print_message "$BLUE" "Building frontend..."
    pnpm --filter @els/shared run build
    pnpm --filter @els/planning-frontend run build

    # Sync to S3
    print_message "$BLUE" "Uploading to S3..."
    aws s3 sync packages/planning-frontend/dist/ "s3://$FRONTEND_BUCKET/" \
        --delete \
        --region "$REGION"

    # Invalidate CloudFront cache
    print_message "$BLUE" "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --region "$REGION" > /dev/null

    print_message "$GREEN" "✓ Frontend deployed to https://$CLOUDFRONT_DOMAIN"
}

# ─── Summary ───
print_summary() {
    print_header "Deployment Complete"

    CLOUDFRONT_DOMAIN=$(get_output PlanningCloudFrontDomainName)
    API_URL=$(get_output PlanningApiGatewayUrl)
    AGENT_ID=$(get_output PlanningBedrockAgentId)

    print_message "$GREEN" "✅ Planning App deployed successfully"
    print_message "$GREEN" "   Frontend:  https://$CLOUDFRONT_DOMAIN"
    print_message "$GREEN" "   API:       $API_URL"
    print_message "$GREEN" "   Agent ID:  $AGENT_ID"
    print_message "$GREEN" "   Stack:     $STACK_NAME"
    print_message "$GREEN" "   Region:    $REGION"

    if [ -n "$CUSTOM_DOMAIN" ]; then
        print_message "$GREEN" "   Domain:    https://$CUSTOM_DOMAIN"
    fi

    echo ""
    print_message "$YELLOW" "API is also available at https://$CLOUDFRONT_DOMAIN/api/*"
}

# ─── Main ───
main() {
    print_header "ELS Planning App Deployment"

    check_prerequisites

    if [ "$SKIP_INFRA" = false ]; then
        deploy_infra
    else
        print_message "$YELLOW" "⏭ Skipping infrastructure deployment"
    fi

    if [ "$SKIP_API" = false ]; then
        deploy_api
    else
        print_message "$YELLOW" "⏭ Skipping Planning API deployment"
    fi

    if [ "$SKIP_ACTION_GROUP" = false ]; then
        deploy_action_group
    else
        print_message "$YELLOW" "⏭ Skipping Action Group deployment"
    fi

    if [ "$SKIP_FRONTEND" = false ]; then
        deploy_frontend
    else
        print_message "$YELLOW" "⏭ Skipping frontend deployment"
    fi

    print_summary
}

main
