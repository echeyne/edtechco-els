#!/bin/bash

# ELS Pipeline Deployment Script (CDK-based)
# Packages Python Lambda code, then deploys infrastructure via CDK.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-pipeline-${ENVIRONMENT}"
SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_message() { echo -e "${1}${2}${NC}"; }
print_header() {
    echo ""
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "$1"
    print_message "$BLUE" "=========================================="
    echo ""
}

SKIP_PACKAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment) ENVIRONMENT="$2"; STACK_NAME="els-pipeline-${ENVIRONMENT}"; shift 2 ;;
        -r|--region) REGION="$2"; shift 2 ;;
        --skip-package) SKIP_PACKAGE=true; shift ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION      AWS region [default: us-east-1]"
            echo "  --skip-package           Skip Lambda packaging (reuse existing S3 zip)"
            echo "  -h, --help               Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                          # Package lambdas + deploy to dev"
            echo "  $0 -e prod                  # Package lambdas + deploy to prod"
            echo "  $0 --skip-package           # Deploy infra only (code already in S3)"
            exit 0 ;;
        *) print_message "$RED" "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Package Lambda code to S3 ───
package_lambdas() {
    print_header "Packaging Lambda Functions"

    if [ -f "$PROJECT_ROOT/scripts/package_lambda.sh" ]; then
        ENVIRONMENT=$ENVIRONMENT AWS_REGION=$REGION bash "$PROJECT_ROOT/scripts/package_lambda.sh"
    else
        print_message "$RED" "❌ scripts/package_lambda.sh not found"
        exit 1
    fi
}

# ─── Deploy via CDK ───
deploy_cdk() {
    print_header "Deploying Pipeline Infrastructure (CDK)"

    print_message "$YELLOW" "Stack: $STACK_NAME | Env: $ENVIRONMENT | Region: $REGION"

    cd "$PROJECT_ROOT/infra/cdk"
    npm ci --silent

    npx cdk deploy "$STACK_NAME" \
        -c environment="$ENVIRONMENT" \
        -c region="$REGION" \
        --require-approval never \
        --output "cdk.out.deploy-${ENVIRONMENT}"

    cd "$PROJECT_ROOT"

    print_message "$GREEN" "✓ Pipeline stack deployed"
}

# ─── Main ───
main() {
    print_header "ELS Pipeline Deployment"

    if [ "$SKIP_PACKAGE" = false ]; then
        package_lambdas
    else
        print_message "$YELLOW" "⏭ Skipping Lambda packaging"
    fi

    deploy_cdk

    print_header "Deployment Complete"
    print_message "$GREEN" "✅ ELS Pipeline deployed: $STACK_NAME ($REGION)"
}

main
