#!/usr/bin/env python3
"""
Manual AWS test script for the Validator module.

This script tests the validator with real AWS S3 storage.

Prerequisites:
1. AWS credentials configured (via ~/.aws/credentials or environment variables)
2. S3 bucket created (els-processed-json or custom bucket name)
3. Required Python packages installed (boto3, pydantic)

Environment Variables:
- ELS_PROCESSED_BUCKET: S3 bucket name for processed JSON (default: els-processed-json)
- AWS_REGION: AWS region (default: us-east-1)
- AWS_PROFILE: AWS profile to use (optional)

Usage:
    python scripts/test_validator_manual.py
"""

import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
from els_pipeline.validator import (
    validate_record,
    serialize_record,
    deserialize_record,
    store_validated_record,
)
from els_pipeline.models import NormalizedStandard, HierarchyLevel
from els_pipeline.config import Config


def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def create_sample_standard():
    """Create a sample NormalizedStandard for testing."""
    return NormalizedStandard(
        standard_id="US-CA-2021-LLD-1.2.a",
        country="US",
        state="CA",
        version_year=2021,
        domain=HierarchyLevel(
            code="LLD",
            name="Language and Literacy Development",
            description=None,
        ),
        strand=HierarchyLevel(
            code="LLD.A",
            name="Listening and Speaking",
            description=None,
        ),
        sub_strand=HierarchyLevel(
            code="LLD.A.1",
            name="Comprehension",
            description=None,
        ),
        indicator=HierarchyLevel(
            code="LLD.A.1.a",
            name="",
            description="Child demonstrates understanding of increasingly complex language.",
        ),
        source_page=43,
        source_text="Sample text from California Preschool Learning Foundations, page 43",
    )


def create_document_meta():
    """Create sample document metadata."""
    return {
        "title": "California Preschool Learning Foundations",
        "source_url": "https://www.cde.ca.gov/sp/cd/re/documents/preschoollf.pdf",
        "age_band": "3-5",
        "publishing_agency": "California Department of Education",
    }


def test_serialization():
    """Test serialization of NormalizedStandard to Canonical JSON."""
    print_section("Test 1: Serialization")
    
    standard = create_sample_standard()
    doc_meta = create_document_meta()
    
    print("Input NormalizedStandard:")
    print(f"  Standard ID: {standard.standard_id}")
    print(f"  State: {standard.state}")
    print(f"  Domain: {standard.domain.code} - {standard.domain.name}")
    print(f"  Strand: {standard.strand.code} - {standard.strand.name}")
    print(f"  Sub-strand: {standard.sub_strand.code} - {standard.sub_strand.name}")
    print(f"  Indicator: {standard.indicator.code}")
    print(f"  Description: {standard.indicator.description}")
    
    canonical = serialize_record(standard, doc_meta)
    
    print("\nSerialized Canonical JSON:")
    print(json.dumps(canonical, indent=2))
    
    return canonical


def test_validation(canonical):
    """Test validation of Canonical JSON."""
    print_section("Test 2: Validation")
    
    print("Validating canonical JSON record...")
    result = validate_record(canonical)
    
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.errors:
        print("\nValidation Errors:")
        for error in result.errors:
            print(f"  - {error.field_path}: {error.message} ({error.error_type})")
    else:
        print("  ✓ Record is valid!")
    
    return result


def test_invalid_record():
    """Test validation with an invalid record."""
    print_section("Test 3: Invalid Record Validation")
    
    standard = create_sample_standard()
    doc_meta = create_document_meta()
    canonical = serialize_record(standard, doc_meta)
    
    # Remove a required field
    del canonical["standard"]["standard_id"]
    
    print("Testing record with missing standard.standard_id...")
    result = validate_record(canonical)
    
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.errors:
        print("\nValidation Errors:")
        for error in result.errors:
            print(f"  - {error.field_path}: {error.message} ({error.error_type})")
    
    assert not result.is_valid, "Invalid record should be rejected"
    print("\n  ✓ Invalid record correctly rejected!")


def test_uniqueness_check():
    """Test Standard_ID uniqueness checking."""
    print_section("Test 4: Standard_ID Uniqueness Check")
    
    standard = create_sample_standard()
    doc_meta = create_document_meta()
    canonical = serialize_record(standard, doc_meta)
    
    # First validation without existing IDs
    print("First validation (no existing IDs)...")
    result1 = validate_record(canonical, existing_ids=set())
    print(f"  Valid: {result1.is_valid}")
    
    # Second validation with the same ID in existing set
    print("\nSecond validation (with existing ID)...")
    existing_ids = {standard.standard_id}
    result2 = validate_record(canonical, existing_ids=existing_ids)
    print(f"  Valid: {result2.is_valid}")
    
    if result2.errors:
        print("\nValidation Errors:")
        for error in result2.errors:
            print(f"  - {error.field_path}: {error.message} ({error.error_type})")
    
    assert not result2.is_valid, "Duplicate ID should be detected"
    print("\n  ✓ Duplicate Standard_ID correctly detected!")


def test_deserialization(canonical):
    """Test deserialization of Canonical JSON back to NormalizedStandard."""
    print_section("Test 5: Deserialization")
    
    print("Deserializing canonical JSON...")
    deserialized = deserialize_record(canonical)
    
    print(f"  Standard ID: {deserialized.standard_id}")
    print(f"  State: {deserialized.state}")
    print(f"  Domain: {deserialized.domain.code} - {deserialized.domain.name}")
    print(f"  Strand: {deserialized.strand.code if deserialized.strand else 'None'}")
    print(f"  Sub-strand: {deserialized.sub_strand.code if deserialized.sub_strand else 'None'}")
    print(f"  Indicator: {deserialized.indicator.code}")
    
    print("\n  ✓ Deserialization successful!")
    return deserialized


def test_s3_storage():
    """Test S3 storage of validated records."""
    print_section("Test 6: S3 Storage")
    
    # Check AWS configuration
    print("AWS Configuration:")
    print(f"  Region: {Config.AWS_REGION}")
    print(f"  Bucket: {Config.S3_PROCESSED_BUCKET}")
    
    # Create S3 client
    try:
        s3_client = boto3.client("s3", region_name=Config.AWS_REGION)
        print("\n  ✓ S3 client created")
    except Exception as e:
        print(f"\n  ✗ Failed to create S3 client: {e}")
        print("\nPlease ensure AWS credentials are configured.")
        return
    
    # Check if bucket exists
    try:
        s3_client.head_bucket(Bucket=Config.S3_PROCESSED_BUCKET)
        print(f"  ✓ Bucket '{Config.S3_PROCESSED_BUCKET}' exists")
    except Exception as e:
        print(f"\n  ✗ Bucket '{Config.S3_PROCESSED_BUCKET}' not found: {e}")
        print(f"\nPlease create the bucket or set ELS_PROCESSED_BUCKET environment variable.")
        return
    
    # Create and store a test record
    standard = create_sample_standard()
    doc_meta = create_document_meta()
    canonical = serialize_record(standard, doc_meta)
    
    # Add timestamp to metadata
    canonical["metadata"]["test_timestamp"] = datetime.utcnow().isoformat()
    
    print("\nStoring record to S3...")
    try:
        s3_key = store_validated_record(canonical, s3_client=s3_client)
        print(f"  ✓ Record stored at: s3://{Config.S3_PROCESSED_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"  ✗ Failed to store record: {e}")
        return
    
    # Verify the record was stored
    print("\nVerifying stored record...")
    try:
        response = s3_client.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET,
            Key=s3_key,
        )
        stored_data = json.loads(response["Body"].read())
        
        print(f"  ✓ Record retrieved successfully")
        print(f"  Standard ID: {stored_data['standard']['standard_id']}")
        print(f"  State: {stored_data['state']}")
        print(f"  Version: {response.get('VersionId', 'N/A')}")
        
    except Exception as e:
        print(f"  ✗ Failed to retrieve record: {e}")
        return
    
    print("\n  ✓ S3 storage test successful!")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  ELS Validator Manual AWS Test")
    print("=" * 80)
    
    try:
        # Test 1: Serialization
        canonical = test_serialization()
        
        # Test 2: Validation
        test_validation(canonical)
        
        # Test 3: Invalid record
        test_invalid_record()
        
        # Test 4: Uniqueness check
        test_uniqueness_check()
        
        # Test 5: Deserialization
        test_deserialization(canonical)
        
        # Test 6: S3 storage (requires AWS credentials)
        test_s3_storage()
        
        print_section("All Tests Complete")
        print("✓ All validator tests passed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
