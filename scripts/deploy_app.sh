#!/bin/bash

# ELS App Deployment Script
# Deploys the frontend (S3 + CloudFront) and API (Lambda + API Gateway)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-app-${ENVIRONMENT}"
TEMPLATE_FILE="infra/app-template.yaml"
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
CUSTOM_DOMAIN=""
HOSTED_ZONE_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            STACK_NAME="els-app-${ENVIRONMENT}"
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
        -d|--domain)
            CUSTOM_DOMAIN="$2"
            shift 2 ;;
        --hosted-zone-id)
            HOSTED_ZONE_ID="$2"
            shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION      AWS region [default: us-east-1]"
            echo "  --skip-infra             Skip CloudFormation deployment"
            echo "  --skip-frontend          Skip frontend build & deploy"
            echo "  --skip-api               Skip API build & deploy"
            echo "  -d, --domain DOMAIN      Custom domain name (e.g. app.example.com)"
            echo "  --hosted-zone-id ID      Route53 Hosted Zone ID for custom domain"
            echo "  -h, --help               Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                # Full deploy to dev"
            echo "  $0 -e prod                        # Full deploy to prod"
            echo "  $0 -e prod -d app.example.com --hosted-zone-id Z1234  # Prod with custom domain"
            echo "  $0 --skip-infra                   # Redeploy code only"
            echo "  $0 --skip-infra --skip-api        # Frontend only"
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
    print_message "$GREEN" "✓ Required tools found"

    if ! aws sts get-caller-identity &> /dev/null; then
        print_message "$RED" "❌ AWS credentials not configured or invalid."
        exit 1
    fi
    print_message "$GREEN" "✓ AWS credentials valid"

    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_message "$RED" "❌ Template not found: $TEMPLATE_FILE"
        exit 1
    fi
    print_message "$GREEN" "✓ CloudFormation template found"
}

# ─── Deploy CloudFormation stack ───
deploy_infra() {
    print_header "Deploying App Infrastructure"

    PIPELINE_STACK="els-pipeline-${ENVIRONMENT}"
    print_message "$YELLOW" "Stack: $STACK_NAME | Env: $ENVIRONMENT | Region: $REGION"
    print_message "$YELLOW" "Pipeline stack: $PIPELINE_STACK"

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

    aws cloudformation deploy \
        --template-file "$TEMPLATE_FILE" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides $PARAM_OVERRIDES \
        --capabilities CAPABILITY_NAMED_IAM \
        --no-fail-on-empty-changeset \
        --region "$REGION"

    print_message "$GREEN" "✓ Infrastructure deployed"
}

# ─── Helper: get stack output ───
get_output() {
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey==\`$1\`].OutputValue" \
        --output text
}

# ─── Build & deploy frontend ───
deploy_frontend() {
    print_header "Building & Deploying Frontend"

    # Get the API URL so the frontend can call it (via CloudFront, so just /api)
    CLOUDFRONT_DOMAIN=$(get_output CloudFrontDomainName)
    FRONTEND_BUCKET=$(get_output FrontendBucketName)
    DISTRIBUTION_ID=$(get_output CloudFrontDistributionId)

    print_message "$YELLOW" "Bucket: $FRONTEND_BUCKET"
    print_message "$YELLOW" "CloudFront: $CLOUDFRONT_DOMAIN"

    # Build
    print_message "$BLUE" "Building frontend..."
    pnpm --filter @els/shared run build
    pnpm --filter @els/frontend run build

    # Sync to S3
    print_message "$BLUE" "Uploading to S3..."
    aws s3 sync packages/frontend/dist/ "s3://$FRONTEND_BUCKET/" \
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

# ─── Build & deploy API ───
deploy_api() {
    print_header "Building & Deploying API"

    LAMBDA_NAME=$(get_output ApiLambdaFunctionName)
    print_message "$YELLOW" "Lambda: $LAMBDA_NAME"

    # Build
    print_message "$BLUE" "Building API..."
    pnpm --filter @els/shared run build
    pnpm --filter @els/api run build

    # Bundle for Lambda using esbuild
    print_message "$BLUE" "Bundling for Lambda..."
    npx esbuild packages/api/dist/lambda.js \
        --bundle \
        --platform=node \
        --target=node24 \
        --format=esm \
        --outfile=build/api-lambda/index.mjs \
        --external:@aws-sdk/* \
        --banner:js="import { createRequire } from 'module'; const require = createRequire(import.meta.url);"

    # Package as zip
    print_message "$BLUE" "Packaging Lambda zip..."
    rm -f build/api-lambda.zip
    (cd build/api-lambda && zip -r ../api-lambda.zip .)

    # Deploy to Lambda
    print_message "$BLUE" "Updating Lambda function code..."
    aws lambda update-function-code \
        --function-name "$LAMBDA_NAME" \
        --zip-file fileb://build/api-lambda.zip \
        --region "$REGION" > /dev/null

    # Wait for update to complete
    aws lambda wait function-updated \
        --function-name "$LAMBDA_NAME" \
        --region "$REGION"

    print_message "$GREEN" "✓ API deployed"
}

# ─── Summary ───
print_summary() {
    print_header "Deployment Complete"

    CLOUDFRONT_DOMAIN=$(get_output CloudFrontDomainName)
    API_URL=$(get_output ApiGatewayUrl)

    print_message "$GREEN" "✅ ELS App deployed successfully"
    print_message "$GREEN" "   Frontend: https://$CLOUDFRONT_DOMAIN"
    print_message "$GREEN" "   API:      $API_URL"
    print_message "$GREEN" "   Stack:    $STACK_NAME"
    print_message "$GREEN" "   Region:   $REGION"
    echo ""
    print_message "$YELLOW" "The API is also available at https://$CLOUDFRONT_DOMAIN/api/*"
}

# ─── Main ───
main() {
    print_header "ELS App Deployment"

    check_prerequisites

    if [ "$SKIP_INFRA" = false ]; then
        deploy_infra
    else
        print_message "$YELLOW" "⏭ Skipping infrastructure deployment"
    fi

    if [ "$SKIP_API" = false ]; then
        deploy_api
    else
        print_message "$YELLOW" "⏭ Skipping API deployment"
    fi

    if [ "$SKIP_FRONTEND" = false ]; then
        deploy_frontend
    else
        print_message "$YELLOW" "⏭ Skipping frontend deployment"
    fi

    print_summary
}

main
