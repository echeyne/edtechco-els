#!/bin/bash

# ELS Pipeline Deployment Script (CDK-based)
# CDK now bundles Python Lambda code automatically via fromAsset with Docker.
# No manual packaging or S3 upload is needed.

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

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment) ENVIRONMENT="$2"; STACK_NAME="els-pipeline-${ENVIRONMENT}"; shift 2 ;;
        -r|--region) REGION="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Environment (dev, staging, prod) [default: dev]"
            echo "  -r, --region REGION      AWS region [default: us-east-1]"
            echo "  -h, --help               Show this help"
            echo ""
            echo "CDK handles Lambda code bundling automatically via Docker."
            echo "When your Python source changes, CDK detects it and deploys new code."
            echo ""
            echo "Examples:"
            echo "  $0                          # Deploy to dev"
            echo "  $0 -e prod                  # Deploy to prod"
            exit 0 ;;
        *) print_message "$RED" "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Deploy via CDK ───
deploy_cdk() {
    print_header "Deploying Pipeline Infrastructure (CDK)"

    print_message "$YELLOW" "Stack: $STACK_NAME | Env: $ENVIRONMENT | Region: $REGION"
    print_message "$YELLOW" "CDK will bundle Python Lambda code automatically via Docker"

    cd "$PROJECT_ROOT/infra/cdk"
    npm ci --silent

    npx cdk deploy "$STACK_NAME" \
        -c environment=$ENVIRONMENT \
        -c region=$REGION \
        --require-approval never \
        --exclusively \
        --output "cdk.out.deploy-${ENVIRONMENT}"

    cd "$PROJECT_ROOT"

    print_message "$GREEN" "✓ Pipeline stack deployed"
}

# ─── Main ───
main() {
    print_header "ELS Pipeline Deployment"

    deploy_cdk

    print_header "Deployment Complete"
    print_message "$GREEN" "✅ ELS Pipeline deployed: $STACK_NAME ($REGION)"
}

main
