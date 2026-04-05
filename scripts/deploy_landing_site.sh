#!/bin/bash

# ELS Landing Site Deployment Script (CDK-based)
# Deploys infrastructure via CDK, then builds and deploys the
# Landing Site frontend (S3 + CloudFront).
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-landing-${ENVIRONMENT}"
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

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment) ENVIRONMENT="$2"; STACK_NAME="els-landing-${ENVIRONMENT}"; shift 2 ;;
        -r|--region) REGION="$2"; shift 2 ;;
        --skip-infra) SKIP_INFRA=true; shift ;;
        --skip-frontend) SKIP_FRONTEND=true; shift ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV       Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION         AWS region [default: us-east-1]"
            echo "  --skip-infra                Skip CDK deployment"
            echo "  --skip-frontend             Skip frontend build & deploy"
            echo "  -h, --help                  Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                          # Full deploy to dev"
            echo "  $0 -e prod                                  # Full deploy to prod"
            echo "  $0 --skip-infra                             # Redeploy frontend only"
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
    print_header "Deploying Landing Site Infrastructure (CDK)"

    cd "$PROJECT_ROOT/infra/cdk"
    npm ci --silent

    CDK_CONTEXT="-c environment=$ENVIRONMENT -c targetStack=$STACK_NAME"

    npx cdk deploy "$STACK_NAME" \
        $CDK_CONTEXT \
        --require-approval never

    cd "$PROJECT_ROOT"
    print_message "$GREEN" "✓ Landing site infrastructure deployed"
}

# ─── Build & deploy frontend ───
deploy_frontend() {
    print_header "Building & Deploying Landing Site Frontend"
    cd "$PROJECT_ROOT"

    FRONTEND_BUCKET=$(get_output LandingSiteBucketName)
    DISTRIBUTION_ID=$(get_output LandingSiteCloudFrontDistributionId)
    CLOUDFRONT_DOMAIN=$(get_output LandingSiteCloudFrontDomainName)

    if [ -z "$FRONTEND_BUCKET" ] || [ -z "$DISTRIBUTION_ID" ]; then
        print_message "$RED" "✗ Failed to retrieve stack outputs from '$STACK_NAME'."
        print_message "$RED" "  Ensure the CDK stack has been deployed (don't use --skip-infra on first deploy)."
        exit 1
    fi

    pnpm --filter @els/landing-site run build

    aws s3 sync packages/landing-site/dist/ "s3://$FRONTEND_BUCKET/" \
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
    CLOUDFRONT_DOMAIN=$(get_output LandingSiteCloudFrontDomainName)
    print_message "$GREEN" "✅ Landing Site deployed"
    print_message "$GREEN" "   Frontend:     https://$CLOUDFRONT_DOMAIN"
    print_message "$GREEN" "   Stack:        $STACK_NAME ($REGION)"
}

# ─── Main ───
main() {
    print_header "ELS Landing Site Deployment"

    if [ "$SKIP_INFRA" = false ]; then
        deploy_infra
    else
        print_message "$YELLOW" "⏭ Skipping infrastructure"
    fi

    if [ "$SKIP_FRONTEND" = false ]; then
        deploy_frontend
    else
        print_message "$YELLOW" "⏭ Skipping frontend"
    fi

    print_summary
}

main
