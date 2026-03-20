#!/bin/bash

# Lambda Packaging Script for ELS Pipeline
# This script packages Python code and dependencies into ZIP files for Lambda deployment

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
BUILD_DIR="build/lambda"
PACKAGE_DIR="$BUILD_DIR/package"

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

# Clean build directory
clean_build() {
    print_header "Cleaning Build Directory"
    
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        print_message "$GREEN" "✓ Cleaned $BUILD_DIR"
    fi
    
    mkdir -p "$PACKAGE_DIR"
    print_message "$GREEN" "✓ Created $BUILD_DIR"
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"
    
    # Check if Docker is available
    if command -v docker &> /dev/null; then
        print_message "$YELLOW" "Using Docker to build Lambda-compatible packages..."
        
        # Use Docker with Amazon Linux 2023 (matches Lambda Python 3.13 runtime)
        # Override entrypoint to run pip directly
        docker run --rm \
            --entrypoint pip \
            -v "$(pwd)/$PACKAGE_DIR:/var/task" \
            public.ecr.aws/lambda/python:3.13 \
            install \
                boto3 \
                pydantic \
                psycopg2-binary \
                python-dotenv \
                --target /var/task \
                --quiet
        
        print_message "$GREEN" "✓ Dependencies installed with Docker (Lambda-compatible)"
    else
        print_message "$YELLOW" "Docker not found, using pip with platform flag..."
        
        # Fallback: Install with platform specification
        pip install --target "$PACKAGE_DIR" \
            --platform manylinux2014_x86_64 \
            --implementation cp \
            --python-version 3.13 \
            --only-binary=:all: \
            boto3 \
            pydantic \
            psycopg2-binary \
            python-dotenv \
            --quiet
        
        print_message "$GREEN" "✓ Dependencies installed with platform flag"
    fi
}

# Copy source code
copy_source() {
    print_header "Copying Source Code"
    
    # Copy the els_pipeline package
    cp -r src/els_pipeline "$PACKAGE_DIR/"
    
    print_message "$GREEN" "✓ Source code copied to $PACKAGE_DIR"
}

# Create Lambda ZIP file
create_zip() {
    local function_name=$1
    print_message "$YELLOW" "Creating ZIP for $function_name..."
    
    cd "$PACKAGE_DIR"
    zip -r "../${function_name}.zip" . -q
    cd - > /dev/null
    
    print_message "$GREEN" "✓ Created $BUILD_DIR/${function_name}.zip"
}

# Package all Lambda functions
package_lambdas() {
    print_header "Packaging Lambda Functions"
    
    # All Lambda functions use the same package (handlers are in els_pipeline.handlers)
    create_zip "els-lambda-package"
    
    print_message "$GREEN" "✓ All Lambda functions packaged"
}

# Upload to S3
upload_to_s3() {
    print_header "Uploading Lambda Packages to S3"
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    # S3 bucket for Lambda code
    LAMBDA_BUCKET="els-lambda-code-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
    
    # Create bucket if it doesn't exist
    if ! aws s3 ls "s3://$LAMBDA_BUCKET" 2>/dev/null; then
        print_message "$YELLOW" "Creating S3 bucket: $LAMBDA_BUCKET"
        aws s3 mb "s3://$LAMBDA_BUCKET" --region "$REGION"
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "$LAMBDA_BUCKET" \
            --versioning-configuration Status=Enabled \
            --region "$REGION"
        
        print_message "$GREEN" "✓ Created bucket: $LAMBDA_BUCKET"
    fi
    
    # Upload ZIP file
    aws s3 cp "$BUILD_DIR/els-lambda-package.zip" \
        "s3://$LAMBDA_BUCKET/els-lambda-package.zip" \
        --region "$REGION"
    
    print_message "$GREEN" "✓ Uploaded Lambda package to S3"
    echo ""
    print_message "$BLUE" "S3 Location: s3://$LAMBDA_BUCKET/els-lambda-package.zip"
}

# Update Lambda functions
update_lambda_functions() {
    print_header "Updating Lambda Functions"
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    LAMBDA_BUCKET="els-lambda-code-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
    
    # List of Lambda function names
    FUNCTIONS=(
        "els-ingester-${ENVIRONMENT}"
        "els-text-extractor-${ENVIRONMENT}"
        "els-structure-detector-${ENVIRONMENT}"
        "els-hierarchy-parser-${ENVIRONMENT}"
        "els-validator-${ENVIRONMENT}"
        "els-persistence-${ENVIRONMENT}"
    )
    
    for func in "${FUNCTIONS[@]}"; do
        print_message "$YELLOW" "Updating $func..."
        
        # Check if function exists
        if aws lambda get-function --function-name "$func" --region "$REGION" &>/dev/null; then
            # Update function code
            aws lambda update-function-code \
                --function-name "$func" \
                --s3-bucket "$LAMBDA_BUCKET" \
                --s3-key "els-lambda-package.zip" \
                --region "$REGION" \
                --output json > /dev/null
            
            print_message "$GREEN" "✓ Updated $func"
        else
            print_message "$YELLOW" "⚠ Function $func does not exist yet (will be created by CloudFormation)"
        fi
    done
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment name (dev, staging, prod) [default: dev]"
    echo "  -r, --region REGION      AWS region [default: us-east-1]"
    echo "  --upload-only            Only upload to S3, don't update functions"
    echo "  --update-only            Only update functions, don't rebuild package"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Package and upload for dev"
    echo "  $0 -e staging -r us-west-2           # Package for staging in us-west-2"
    echo "  $0 --upload-only                     # Only upload existing package"
    echo "  $0 --update-only                     # Only update Lambda functions"
}

# Parse command line arguments
UPLOAD_ONLY=false
UPDATE_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        --upload-only)
            UPLOAD_ONLY=true
            shift
            ;;
        --update-only)
            UPDATE_ONLY=true
            shift
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
    print_header "Lambda Packaging for ELS Pipeline"
    print_message "$BLUE" "Environment: $ENVIRONMENT"
    print_message "$BLUE" "Region: $REGION"
    
    if [ "$UPDATE_ONLY" = true ]; then
        update_lambda_functions
    elif [ "$UPLOAD_ONLY" = true ]; then
        upload_to_s3
        update_lambda_functions
    else
        clean_build
        install_dependencies
        copy_source
        package_lambdas
        upload_to_s3
        update_lambda_functions
    fi
    
    print_header "Packaging Complete"
    print_message "$GREEN" "✅ Lambda functions packaged and deployed!"
}

# Run main function
main
