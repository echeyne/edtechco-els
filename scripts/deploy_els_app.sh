#!/bin/bash

# ELS App Deployment Script (CDK-based)
# Deploys infrastructure via CDK, then builds and deploys the API Lambda
# and frontend (S3 + CloudFront).

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-app-${ENVIRONMENT}"
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

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment) ENVIRONMENT="$2"; STACK_NAME="els-app-${ENVIRONMENT}"; shift 2 ;;
        -r|--region) REGION="$2"; shift 2 ;;
        --skip-infra) SKIP_INFRA=true; shift ;;
        --skip-frontend) SKIP_FRONTEND=true; shift ;;
        --skip-api) SKIP_API=true; shift ;;
        -d|--domain) CUSTOM_DOMAIN="$2"; shift 2 ;;
        --hosted-zone-id) HOSTED_ZONE_ID="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION      AWS region [default: us-east-1]"
            echo "  --skip-infra             Skip CDK deployment"
            echo "  --skip-frontend          Skip frontend build & deploy"
            echo "  --skip-api               Skip API build & deploy"
            echo "  -d, --domain DOMAIN      Custom domain name (e.g. app.example.com)"
            echo "  --hosted-zone-id ID      Route53 Hosted Zone ID for custom domain"
            echo "  -h, --help               Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                # Full deploy to dev"
            echo "  $0 -e prod -d app.example.com --hosted-zone-id Z1234"
            echo "  $0 --skip-infra                   # Redeploy code only"
            echo "  $0 --skip-infra --skip-api        # Frontend only"
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

# ─── Deploy CDK stack ───
deploy_infra() {
    print_header "Deploying App Infrastructure (CDK)"

    if [ -z "$DESCOPE_PROJECT_ID" ]; then
        print_message "$RED" "❌ DESCOPE_PROJECT_ID environment variable is required"
        exit 1
    fi

    cd "$PROJECT_ROOT/infra/cdk"
    npm ci --silent

    CDK_CONTEXT="-c environment=$ENVIRONMENT"
    [ -n "$CUSTOM_DOMAIN" ] && CDK_CONTEXT="$CDK_CONTEXT -c customDomain=$CUSTOM_DOMAIN"
    [ -n "$HOSTED_ZONE_ID" ] && CDK_CONTEXT="$CDK_CONTEXT -c hostedZoneId=$HOSTED_ZONE_ID"

    DESCOPE_PROJECT_ID="$DESCOPE_PROJECT_ID" npx cdk deploy "$STACK_NAME" \
        $CDK_CONTEXT \
        --require-approval never

    cd "$PROJECT_ROOT"
    print_message "$GREEN" "✓ Infrastructure deployed"
}

# ─── Build & deploy API ───
deploy_api() {
    print_header "API Code Deployed via CDK"
    print_message "$GREEN" "✓ CDK bundles and deploys the API Lambda code automatically."
    print_message "$GREEN" "  If you skipped infra, re-run without --skip-infra to deploy code changes."
}

# ─── Build & deploy frontend ───
deploy_frontend() {
    print_header "Building & Deploying Frontend"

    FRONTEND_BUCKET=$(get_output FrontendBucketName)
    DISTRIBUTION_ID=$(get_output CloudFrontDistributionId)
    CLOUDFRONT_DOMAIN=$(get_output CloudFrontDomainName)

    API_URL=$(get_output ApiGatewayUrl)
    echo "VITE_API_BASE=$API_URL" > packages/els-explorer-frontend/.env.production.local

    pnpm --filter @els/shared run build
    pnpm --filter @els/frontend run build

    rm -f packages/els-explorer-frontend/.env.production.local

    aws s3 sync packages/els-explorer-frontend/dist/ "s3://$FRONTEND_BUCKET/" \
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
    CLOUDFRONT_DOMAIN=$(get_output CloudFrontDomainName)
    API_URL=$(get_output ApiGatewayUrl)
    print_message "$GREEN" "✅ ELS App deployed"
    print_message "$GREEN" "   Frontend: https://$CLOUDFRONT_DOMAIN"
    print_message "$GREEN" "   API:      $API_URL"
    print_message "$GREEN" "   Stack:    $STACK_NAME ($REGION)"
}

# ─── Main ───
main() {
    print_header "ELS App Deployment"

    [ "$SKIP_INFRA" = false ] && deploy_infra || print_message "$YELLOW" "⏭ Skipping infrastructure"
    [ "$SKIP_API" = false ] && deploy_api || print_message "$YELLOW" "⏭ Skipping API"
    [ "$SKIP_FRONTEND" = false ] && deploy_frontend || print_message "$YELLOW" "⏭ Skipping frontend"

    print_summary
}

main
