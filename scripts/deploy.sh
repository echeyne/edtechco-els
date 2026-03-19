#!/bin/bash

# ELS Pipeline Deployment Script
# This script deploys the ELS Normalization Pipeline to AWS
# Supports country-based path structures for multi-country deployments

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="els-pipeline-${ENVIRONMENT}"
TEMPLATE_FILE="infra/template.yaml"

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print section header
print_header() {
    echo ""
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "$1"
    print_message "$BLUE" "=========================================="
    echo ""
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_message "$RED" "❌ AWS CLI not found. Please install it first."
        exit 1
    fi
    print_message "$GREEN" "✓ AWS CLI found: $(aws --version)"
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_message "$RED" "❌ AWS credentials not configured or invalid."
        exit 1
    fi
    print_message "$GREEN" "✓ AWS credentials configured"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_message "$RED" "❌ Python 3 not found. Please install it first."
        exit 1
    fi
    print_message "$GREEN" "✓ Python found: $(python3 --version)"
    
    # Check template file
    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_message "$RED" "❌ CloudFormation template not found: $TEMPLATE_FILE"
        exit 1
    fi
    print_message "$GREEN" "✓ CloudFormation template found"
}

# Package Lambda functions
package_lambdas() {
    print_header "Packaging Lambda Functions"
    
    if [ -f "scripts/package_lambda.sh" ]; then
        ENVIRONMENT=$ENVIRONMENT AWS_REGION=$REGION bash scripts/package_lambda.sh
    else
        print_message "$RED" "❌ Lambda packaging script not found"
        exit 1
    fi
}

# Validate CloudFormation template
validate_template() {
    print_header "Validating CloudFormation Template"

    # Template exceeds 51,200 byte inline limit — upload to S3 for validation
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    CFN_BUCKET="els-lambda-code-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"

    aws s3 cp "$TEMPLATE_FILE" "s3://$CFN_BUCKET/cfn-templates/template.yaml" \
        --region "$REGION" > /dev/null

    TEMPLATE_URL="https://${CFN_BUCKET}.s3.${REGION}.amazonaws.com/cfn-templates/template.yaml"

    if aws cloudformation validate-template \
        --template-url "$TEMPLATE_URL" \
        --region "$REGION" > /dev/null 2>&1; then
        print_message "$GREEN" "✓ Template validation successful"
    else
        print_message "$RED" "❌ Template validation failed"
        exit 1
    fi
}

# Deploy CloudFormation stack
deploy_stack() {
    print_header "Deploying CloudFormation Stack"
    
    print_message "$YELLOW" "Stack Name: $STACK_NAME"
    print_message "$YELLOW" "Environment: $ENVIRONMENT"
    print_message "$YELLOW" "Region: $REGION"
    echo ""

    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    CFN_BUCKET="els-lambda-code-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"

    aws cloudformation deploy \
        --template-file $TEMPLATE_FILE \
        --stack-name $STACK_NAME \
        --parameter-overrides \
            EnvironmentName=$ENVIRONMENT \
            Region=$REGION \
        --capabilities CAPABILITY_NAMED_IAM \
        --no-fail-on-empty-changeset \
        --s3-bucket "$CFN_BUCKET" \
        --s3-prefix cfn-templates \
        --region $REGION
    
    if [ $? -eq 0 ]; then
        print_message "$GREEN" "✓ Stack deployment successful"
    else
        print_message "$RED" "❌ Stack deployment failed"
        exit 1
    fi
}

# Get and display stack outputs
get_stack_outputs() {
    print_header "Stack Outputs"
    
    # Get all outputs
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs' \
        --output json)
    
    # Parse specific outputs
    RAW_BUCKET=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="RawDocumentsBucketName") | .OutputValue')
    PROCESSED_BUCKET=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="ProcessedJsonBucketName") | .OutputValue')
    
    print_message "$GREEN" "Raw Documents Bucket: $RAW_BUCKET"
    print_message "$GREEN" "Processed JSON Bucket: $PROCESSED_BUCKET"
    echo ""
    print_message "$YELLOW" "S3 Path Structure:"
    print_message "$YELLOW" "  Raw: {country}/{state}/{year}/{filename}"
    print_message "$YELLOW" "  Processed: {country}/{state}/{year}/{standard_id}.json"
    echo ""
    print_message "$YELLOW" "Example paths:"
    print_message "$YELLOW" "  s3://$RAW_BUCKET/US/CA/2021/california_standards.pdf"
    print_message "$YELLOW" "  s3://$PROCESSED_BUCKET/US/CA/2021/US-CA-2021-LLD-1.2.json"
}

# Create example .env file
create_env_file() {
    print_header "Creating Environment Configuration"
    
    if [ -f ".env" ]; then
        print_message "$YELLOW" "⚠ .env file already exists, creating .env.${ENVIRONMENT}"
        ENV_FILE=".env.${ENVIRONMENT}"
    else
        ENV_FILE=".env"
    fi
    
    RAW_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
        --output text)
    
    PROCESSED_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ProcessedJsonBucketName`].OutputValue' \
        --output text)
    
    cat > $ENV_FILE << EOF
# ELS Pipeline Environment Configuration
# Generated on $(date)
# Environment: $ENVIRONMENT
# Region: $REGION

# AWS Configuration
AWS_REGION=$REGION
ENVIRONMENT=$ENVIRONMENT

# S3 Buckets
ELS_RAW_BUCKET=$RAW_BUCKET
ELS_PROCESSED_BUCKET=$PROCESSED_BUCKET

# S3 Path Structure (country-based)
# Raw documents: {country}/{state}/{year}/{filename}
# Processed JSON: {country}/{state}/{year}/{standard_id}.json
# Example: US/CA/2021/california_standards.pdf

# Country Code Validation
COUNTRY_CODE_VALIDATION=enabled

# Bedrock Configuration (update with your model IDs)
BEDROCK_DETECTOR_LLM_MODEL_ID=us.anthropic.claude-opus-4-6-v1
BEDROCK_PARSER_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-6
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Confidence Threshold
CONFIDENCE_THRESHOLD=0.7

# Database Configuration (update after Aurora deployment)
# DB_HOST=
# DB_PORT=5432
# DB_NAME=els_pipeline
# DB_USER=
# DB_PASSWORD=
EOF
    
    print_message "$GREEN" "✓ Environment file created: $ENV_FILE"
}

# Verify deployment
verify_deployment() {
    print_header "Verifying Deployment"
    
    # Check stack status
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].StackStatus' \
        --output text)
    
    if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
        print_message "$GREEN" "✓ Stack status: $STACK_STATUS"
    else
        print_message "$RED" "❌ Stack status: $STACK_STATUS"
        exit 1
    fi
    
    # Check S3 buckets
    RAW_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
        --output text)
    
    if aws s3 ls "s3://$RAW_BUCKET" &> /dev/null; then
        print_message "$GREEN" "✓ Raw documents bucket accessible"
    else
        print_message "$RED" "❌ Raw documents bucket not accessible"
    fi
    
    PROCESSED_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ProcessedJsonBucketName`].OutputValue' \
        --output text)
    
    if aws s3 ls "s3://$PROCESSED_BUCKET" &> /dev/null; then
        print_message "$GREEN" "✓ Processed JSON bucket accessible"
    else
        print_message "$RED" "❌ Processed JSON bucket not accessible"
    fi
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment name (dev, staging, prod) [default: dev]"
    echo "  -r, --region REGION      AWS region [default: us-east-1]"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  ENVIRONMENT              Environment name (overridden by -e)"
    echo "  AWS_REGION               AWS region (overridden by -r)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy to dev in us-east-1"
    echo "  $0 -e staging -r us-west-2           # Deploy to staging in us-west-2"
    echo "  ENVIRONMENT=prod $0                   # Deploy to prod using env var"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            STACK_NAME="els-pipeline-${ENVIRONMENT}"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_message "$RED" "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header "ELS Pipeline Deployment"
    print_message "$BLUE" "Starting deployment process..."
    
    check_prerequisites
    package_lambdas
    validate_template
    deploy_stack
    get_stack_outputs
    create_env_file
    verify_deployment
    
    print_header "Deployment Complete"
    print_message "$GREEN" "✅ ELS Pipeline deployed successfully!"
    print_message "$GREEN" "Stack: $STACK_NAME"
    print_message "$GREEN" "Region: $REGION"
    print_message "$GREEN" "Environment: $ENVIRONMENT"
    echo ""
    print_message "$YELLOW" "Next steps:"
    print_message "$YELLOW" "1. Review the generated .env file"
    print_message "$YELLOW" "2. Update database credentials after Aurora deployment"
    print_message "$YELLOW" "3. Test document ingestion with country codes"
    print_message "$YELLOW" "4. Monitor CloudWatch logs for Lambda functions"
}

# Run main function
main
