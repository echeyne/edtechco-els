#!/bin/bash

# ============================================================================
# CloudFormation → CDK Migration Script
#
# This script migrates existing CloudFormation stacks to CDK management
# WITHOUT deleting or recreating any AWS resources.
#
# Strategy:
#   1. Delete each CFN stack with --retain-resources (orphans resources, deletes nothing)
#   2. Use `cdk import` to adopt orphaned resources into CDK-managed stacks
#
# Order matters: dependent stacks (app, planning) must be deleted BEFORE
# the pipeline stack because they import cross-stack exports from it.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - CDK bootstrapped in the target account/region
#   - Run from the project root directory

# ENVIRONMENT=dev AWS_REGION=us-east-1 DESCOPE_PROJECT_ID=your-id ./scripts/migrate_cfn_to_cdk.sh

# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
CDK_DIR="infra/cdk"

print_msg() { echo -e "${1}${2}${NC}"; }
print_header() {
    echo ""
    print_msg "$BLUE" "=========================================="
    print_msg "$BLUE" "$1"
    print_msg "$BLUE" "=========================================="
    echo ""
}

# Stack names
PIPELINE_STACK="els-pipeline-${ENVIRONMENT}"
APP_STACK="els-app-${ENVIRONMENT}"
PLANNING_STACK="els-planning-${ENVIRONMENT}"

# ── Helper: check if a stack exists ──
stack_exists() {
    local stack_name="$1"
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "Stacks[0].StackStatus" \
        --output text 2>/dev/null
}

# ── Helper: set DeletionPolicy=Retain on all resources, then delete stack ──
# CloudFormation only allows --retain-resources on DELETE_FAILED stacks.
# For normal stacks we must first update the template so every resource has
# DeletionPolicy: Retain, then delete — CFN will remove the stack from its
# registry but leave all physical resources untouched.
orphan_stack() {
    local stack_name="$1"

    print_msg "$BLUE" "  Fetching current template for $stack_name..."
    local template
    template=$(aws cloudformation get-template \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "TemplateBody" \
        --output json 2>/dev/null)

    # Write the template to a temp file so we can manipulate it
    local tmp_template
    tmp_template=$(mktemp /tmp/cfn-migrate-XXXXXX.json)

    # Use node to add DeletionPolicy: Retain to every resource
    node -e "
        const tpl = JSON.parse(process.argv[1]);
        for (const [id, res] of Object.entries(tpl.Resources || {})) {
            res.DeletionPolicy = 'Retain';
        }
        require('fs').writeFileSync('$tmp_template', JSON.stringify(tpl));
    " "$template"

    print_msg "$BLUE" "  Updating $stack_name with DeletionPolicy: Retain on all resources..."

    # Get current parameters to pass through unchanged
    local params
    params=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "Stacks[0].Parameters[].{ParameterKey:ParameterKey,UsePreviousValue:\`true\`}" \
        --output json 2>/dev/null)

    if [ "$params" = "null" ] || [ "$params" = "[]" ] || [ -z "$params" ]; then
        aws cloudformation update-stack \
            --stack-name "$stack_name" \
            --region "$REGION" \
            --template-body "file://$tmp_template" \
            --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
            --no-cli-pager 2>/dev/null || true
    else
        aws cloudformation update-stack \
            --stack-name "$stack_name" \
            --region "$REGION" \
            --template-body "file://$tmp_template" \
            --parameters "$params" \
            --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
            --no-cli-pager 2>/dev/null || true
    fi

    print_msg "$BLUE" "  Waiting for update to complete..."
    aws cloudformation wait stack-update-complete \
        --stack-name "$stack_name" \
        --region "$REGION" 2>/dev/null || true

    print_msg "$BLUE" "  Deleting $stack_name (resources will be retained)..."
    aws cloudformation delete-stack \
        --stack-name "$stack_name" \
        --region "$REGION"

    print_msg "$BLUE" "  Waiting for $stack_name deletion..."
    aws cloudformation wait stack-delete-complete \
        --stack-name "$stack_name" \
        --region "$REGION"

    rm -f "$tmp_template"
    print_msg "$GREEN" "  ✓ $stack_name deleted (all resources retained)"
}

# ── Step 0: Preflight checks ──
print_header "Preflight Checks"

for stack in "$PLANNING_STACK" "$APP_STACK" "$PIPELINE_STACK"; do
    status=$(stack_exists "$stack" || echo "DOES_NOT_EXIST")
    if [ "$status" = "DOES_NOT_EXIST" ]; then
        print_msg "$YELLOW" "  Stack $stack does not exist — skipping"
    else
        print_msg "$GREEN" "  Stack $stack exists (status: $status)"
    fi
done

echo ""
print_msg "$YELLOW" "This will:"
print_msg "$YELLOW" "  1. Delete CloudFormation stacks (retaining ALL resources)"
print_msg "$YELLOW" "  2. Import resources into CDK-managed stacks"
print_msg "$YELLOW" ""
print_msg "$YELLOW" "No AWS resources will be deleted or recreated."
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_msg "$RED" "Aborted."
    exit 1
fi

# ── Step 1: Delete dependent stacks first (retain all resources) ──
print_header "Step 1: Orphan resources from dependent stacks"

for stack in "$PLANNING_STACK" "$APP_STACK"; do
    status=$(stack_exists "$stack" || echo "DOES_NOT_EXIST")
    if [ "$status" = "DOES_NOT_EXIST" ]; then
        print_msg "$YELLOW" "  $stack does not exist, skipping"
        continue
    fi

    orphan_stack "$stack"
done

# ── Step 2: Delete the pipeline stack (retain all resources) ──
print_header "Step 2: Orphan resources from pipeline stack"

status=$(stack_exists "$PIPELINE_STACK" || echo "DOES_NOT_EXIST")
if [ "$status" = "DOES_NOT_EXIST" ]; then
    print_msg "$YELLOW" "  $PIPELINE_STACK does not exist, skipping"
else
    orphan_stack "$PIPELINE_STACK"
fi

# ── Step 3: Import resources into CDK stacks (pipeline first) ──
print_header "Step 3: Import resources into CDK stacks"

print_msg "$BLUE" "  Importing $PIPELINE_STACK..."
print_msg "$YELLOW" "  CDK will prompt you for physical resource IDs."
print_msg "$YELLOW" "  For each resource, enter the actual AWS resource ID/ARN."
echo ""

(cd "$CDK_DIR" && DESCOPE_PROJECT_ID="${DESCOPE_PROJECT_ID:-placeholder}" \
    npx cdk import "$PIPELINE_STACK" \
    --context environment="$ENVIRONMENT" \
    --context region="$REGION")

print_msg "$GREEN" "  ✓ $PIPELINE_STACK imported into CDK"

print_msg "$BLUE" "  Importing $APP_STACK..."
echo ""

(cd "$CDK_DIR" && DESCOPE_PROJECT_ID="${DESCOPE_PROJECT_ID:-placeholder}" \
    npx cdk import "$APP_STACK" \
    --context environment="$ENVIRONMENT" \
    --context region="$REGION")

print_msg "$GREEN" "  ✓ $APP_STACK imported into CDK"

print_msg "$BLUE" "  Importing $PLANNING_STACK..."
echo ""

(cd "$CDK_DIR" && DESCOPE_PROJECT_ID="${DESCOPE_PROJECT_ID:-placeholder}" \
    npx cdk import "$PLANNING_STACK" \
    --context environment="$ENVIRONMENT" \
    --context region="$REGION")

print_msg "$GREEN" "  ✓ $PLANNING_STACK imported into CDK"

# ── Step 4: Verify ──
print_header "Step 4: Verify"

print_msg "$BLUE" "  Running cdk diff to check for remaining differences..."
echo ""

(cd "$CDK_DIR" && DESCOPE_PROJECT_ID="${DESCOPE_PROJECT_ID:-placeholder}" \
    npx cdk diff \
    --context environment="$ENVIRONMENT" \
    --context region="$REGION" 2>&1) || true

echo ""
print_header "Migration Complete"
print_msg "$GREEN" "All stacks are now managed by CDK."
print_msg "$GREEN" "Future deployments: use 'cdk deploy' instead of 'aws cloudformation deploy'."
