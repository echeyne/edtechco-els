#!/bin/bash

# ELS Planning App Deployment Script (CDK-based)
# Deploys infrastructure (including AgentCore Runtime) via CDK, then builds
# and deploys the Planning API Lambda and frontend (S3 + CloudFront).
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-planning-${ENVIRONMENT}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_message() { echo -e "${1}${2}${NC}"; }
print_header() {
    echo ""
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "$1"
    print_message "$BLUE" "=========================================="
    echo ""
}

SKIP_INFRA=false
SKIP_FRONTEND=false
SKIP_API=false
CUSTOM_DOMAIN=""
HOSTED_ZONE_ID=""
BEDROCK_MODEL_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment) ENVIRONMENT="$2"; STACK_NAME="els-planning-${ENVIRONMENT}"; shift 2 ;;
        -r|--region) REGION="$2"; shift 2 ;;
        --skip-infra) SKIP_INFRA=true; shift ;;
        --skip-frontend) SKIP_FRONTEND=true; shift ;;
        --skip-api) SKIP_API=true; shift ;;
        -d|--domain) CUSTOM_DOMAIN="$2"; shift 2 ;;
        --hosted-zone-id) HOSTED_ZONE_ID="$2"; shift 2 ;;
        --bedrock-model) BEDROCK_MODEL_ID="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV       Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION         AWS region [default: us-east-1]"
            echo "  --skip-infra                Skip CDK deployment (infra + AgentCore Runtime)"
            echo "  --skip-frontend             Skip frontend build & deploy"
            echo "  --skip-api                  Skip Planning API Lambda deploy"
            echo "  -d, --domain DOMAIN         Custom domain (e.g. plan.example.com)"
            echo "  --hosted-zone-id ID         Route53 Hosted Zone ID for custom domain"
            echo "  --bedrock-model MODEL_ID    Bedrock model ID [default: template default]"
            echo "  -h, --help                  Show this help"
            echo ""
            echo "Environment Variables:"
            echo "  DESCOPE_PROJECT_ID          (required) Descope project ID for auth"
            echo ""
            echo "Examples:"
            echo "  $0                                          # Full deploy to dev"
            echo "  $0 -e prod -d plan.example.com --hosted-zone-id Z1234"
            echo "  $0 --skip-infra                             # Redeploy code only"
            echo "  $0 --skip-infra --skip-frontend             # API only"
            exit 0 ;;
        *) print_message "$RED" "Unknown option: $1"; exit 1 ;;
    esac
done

get_output() {
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey==\`$1\`].OutputValue" \
        --output text
}

# ─── Deploy CDK stack (infra + AgentCore Runtime) ───
deploy_infra() {
    print_header "Deploying Planning Infrastructure + AgentCore (CDK)"

    if [ -z "$DESCOPE_PROJECT_ID" ]; then
        print_message "$RED" "❌ DESCOPE_PROJECT_ID environment variable is required"
        exit 1
    fi

    cd "$PROJECT_ROOT/infra/cdk"
    npm ci --silent

    CDK_CONTEXT="-c environment=$ENVIRONMENT"
    [ -n "$CUSTOM_DOMAIN" ] && CDK_CONTEXT="$CDK_CONTEXT -c planningDomain=$CUSTOM_DOMAIN"
    [ -n "$HOSTED_ZONE_ID" ] && CDK_CONTEXT="$CDK_CONTEXT -c hostedZoneId=$HOSTED_ZONE_ID"
    [ -n "$BEDROCK_MODEL_ID" ] && CDK_CONTEXT="$CDK_CONTEXT -c bedrockModel=$BEDROCK_MODEL_ID"

    DESCOPE_PROJECT_ID="$DESCOPE_PROJECT_ID" npx cdk deploy "$STACK_NAME" \
        $CDK_CONTEXT \
        --require-approval never

    cd "$PROJECT_ROOT"
    print_message "$GREEN" "✓ Infrastructure + AgentCore Runtime deployed"
}

# ─── Build & deploy Planning API Lambda ───
deploy_api() {
    print_header "Building & Deploying Planning API"
    cd "$PROJECT_ROOT"

    LAMBDA_NAME=$(get_output PlanningApiLambdaFunctionName)
    print_message "$YELLOW" "Lambda: $LAMBDA_NAME"

    pnpm --filter @els/shared run build
    pnpm --filter @els/planning-api run build

    mkdir -p build/planning-api-lambda

    npx esbuild packages/planning-api/dist/lambda.js \
        --bundle \
        --platform=node \
        --target=node20 \
        --format=esm \
        --outfile=build/planning-api-lambda/index.mjs \
        '--external:@aws-sdk/*' \
        --banner:js="import { createRequire } from 'module'; const require = createRequire(import.meta.url);"

    rm -f build/planning-api-lambda.zip
    (cd build/planning-api-lambda && zip -r ../planning-api-lambda.zip .)

    aws lambda update-function-code \
        --function-name "$LAMBDA_NAME" \
        --zip-file fileb://build/planning-api-lambda.zip \
        --region "$REGION" > /dev/null

    aws lambda wait function-updated \
        --function-name "$LAMBDA_NAME" \
        --region "$REGION"

    print_message "$GREEN" "✓ Planning API deployed"
}

# ─── Build & deploy frontend ───
deploy_frontend() {
    print_header "Building & Deploying Planning Frontend"
    cd "$PROJECT_ROOT"

    FRONTEND_BUCKET=$(get_output PlanningFrontendBucketName)
    DISTRIBUTION_ID=$(get_output PlanningCloudFrontDistributionId)
    CLOUDFRONT_DOMAIN=$(get_output PlanningCloudFrontDomainName)

    pnpm --filter @els/shared run build
    pnpm --filter @els/planning-frontend run build

    aws s3 sync packages/planning-frontend/dist/ "s3://$FRONTEND_BUCKET/" \
        --delete --region "$REGION"

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
    RUNTIME_ARN=$(get_output PlanningAgentCoreRuntimeArn)
    print_message "$GREEN" "✅ Planning App deployed"
    print_message "$GREEN" "   Frontend:     https://$CLOUDFRONT_DOMAIN"
    print_message "$GREEN" "   API:          $API_URL"
    print_message "$GREEN" "   AgentCore:    $RUNTIME_ARN"
    print_message "$GREEN" "   Stack:        $STACK_NAME ($REGION)"
}

# ─── Main ───
main() {
    print_header "ELS Planning App Deployment"

    [ "$SKIP_INFRA" = false ] && deploy_infra || print_message "$YELLOW" "⏭ Skipping infrastructure"
    [ "$SKIP_API" = false ] && deploy_api || print_message "$YELLOW" "⏭ Skipping API"
    [ "$SKIP_FRONTEND" = false ] && deploy_frontend || print_message "$YELLOW" "⏭ Skipping frontend"

    print_summary
}

main
