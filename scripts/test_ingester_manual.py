#!/usr/bin/env python3
"""Manual test script for ingester with real AWS S3.

This script tests the ingester against a real AWS S3 bucket.
Use this after deploying your CloudFormation stack to verify
the ingester works with actual AWS infrastructure.

Prerequisites:
1. Deploy CloudFormation stack (infra/template.yaml)
2. Set environment variables (see instructions below)
3. Ensure AWS credentials are configured (aws configure)
4. Have a test document ready to upload

Usage:
    python scripts/test_ingester_manual.py
"""

import sys
import os
from pathlib import Path

# Add src to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from els_pipeline.ingester import ingest_document
from els_pipeline.models import IngestionRequest
from els_pipeline.config import Config


def print_config():
    """Print current configuration."""
    print("=" * 60)
    print("Current Configuration:")
    print("=" * 60)
    print(f"S3 Raw Bucket:  {Config.S3_RAW_BUCKET}")
    print(f"AWS Region:     {Config.AWS_REGION}")
    print("=" * 60)
    print()


def test_california_standards():
    """Test ingestion of California standards document."""
    print("Testing California Standards Ingestion")
    print("-" * 60)
    
    # Path to the California standards PDF
    file_path = "standards/california_all_standards_2021.pdf"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        print(f"   Please ensure the file exists before running this test.")
        return False
    
    print(f"📄 File: {file_path}")
    file_size = os.path.getsize(file_path)
    print(f"📊 Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print()
    
    # Create ingestion request
    request = IngestionRequest(
        file_path=file_path,
        country="US",
        state="CA",
        version_year=2021,
        source_url="https://www.cde.ca.gov/sp/cd/re/documents/ptklfataglance.pdf",
        publishing_agency="California Department of Education",
        filename="california_all_standards_2021.pdf"
    )
    
    print("🚀 Starting ingestion...")
    print()
    
    try:
        result = ingest_document(request)
        
        print("=" * 60)
        print("Ingestion Result:")
        print("=" * 60)
        print(f"Status:      {result.status}")
        print(f"S3 Key:      {result.s3_key}")
        print(f"Version ID:  {result.s3_version_id}")
        
        if result.error:
            print(f"Error:       {result.error}")
        
        print()
        print("Metadata:")
        for key, value in result.metadata.items():
            print(f"  {key:20s}: {value}")
        
        print("=" * 60)
        
        if result.status == "success":
            print()
            print("✅ SUCCESS! Document uploaded to S3.")
            print()
            print("Verification commands:")
            print(f"  aws s3 ls s3://{Config.S3_RAW_BUCKET}/{result.s3_key}")
            print(f"  aws s3api head-object --bucket {Config.S3_RAW_BUCKET} --key {result.s3_key}")
            print()
            return True
        else:
            print()
            print("❌ FAILED! See error above.")
            print()
            return False
            
    except Exception as e:
        print("=" * 60)
        print(f"❌ Exception occurred: {type(e).__name__}")
        print(f"   {str(e)}")
        print("=" * 60)
        return False


def main():
    """Main test function."""
    print()
    print("=" * 60)
    print("ELS Pipeline - Manual Ingester Test")
    print("=" * 60)
    print()
    
    # Check environment variables
    if Config.S3_RAW_BUCKET == "els-raw-documents":
        print("⚠️  WARNING: Using default bucket name.")
        print("   You may need to set ELS_RAW_BUCKET environment variable.")
        print()
        print("   After deploying CloudFormation, set:")
        print("   export ELS_RAW_BUCKET='els-raw-documents-dev-<account-id>'")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting.")
            return
        print()
    
    print_config()
    
    # Run test
    success = test_california_standards()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
