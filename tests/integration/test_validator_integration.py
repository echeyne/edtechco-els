"""Integration tests for validator module with mocked S3."""

import pytest
import json
from moto import mock_aws
import boto3
from els_pipeline.validator import (
    validate_record,
    serialize_record,
    deserialize_record,
    store_validated_record,
)
from els_pipeline.models import NormalizedStandard, HierarchyLevel
from els_pipeline.config import Config


@pytest.fixture
def s3_client():
    """Create a mocked S3 client."""
    with mock_aws():
        client = boto3.client("s3", region_name=Config.AWS_REGION)
        # Create the processed bucket
        client.create_bucket(Bucket=Config.S3_PROCESSED_BUCKET)
        yield client


@pytest.fixture
def sample_standard():
    """Create a sample NormalizedStandard."""
    return NormalizedStandard(
        standard_id="US-CA-2021-LLD-1.2",
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
        source_text="Sample text from page 43",
    )


@pytest.fixture
def sample_document_meta():
    """Create sample document metadata."""
    return {
        "title": "California Preschool Learning Foundations",
        "source_url": "https://www.cde.ca.gov/sp/cd/re/documents/preschoollf.pdf",
        "age_band": "3-5",
        "publishing_agency": "California Department of Education",
    }


def test_schema_validation_with_valid_record(sample_standard, sample_document_meta):
    """Test schema validation with a valid record."""
    # Serialize the standard
    record = serialize_record(sample_standard, sample_document_meta)
    
    # Validate
    result = validate_record(record)
    
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert result.record is not None


def test_schema_validation_with_missing_state(sample_standard, sample_document_meta):
    """Test schema validation with missing state field."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["state"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any(error.field_path == "state" for error in result.errors)


def test_schema_validation_with_missing_country(sample_standard, sample_document_meta):
    """Test schema validation with missing country field."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["country"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any(error.field_path == "country" for error in result.errors)


def test_schema_validation_with_missing_document_title(sample_standard, sample_document_meta):
    """Test schema validation with missing document.title."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["document"]["title"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any(error.field_path == "document.title" for error in result.errors)


def test_schema_validation_with_missing_standard_id(sample_standard, sample_document_meta):
    """Test schema validation with missing standard.standard_id."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["standard"]["standard_id"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any(error.field_path == "standard.standard_id" for error in result.errors)


def test_schema_validation_with_missing_domain_code(sample_standard, sample_document_meta):
    """Test schema validation with missing standard.domain.code."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["standard"]["domain"]["code"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any(error.field_path == "standard.domain.code" for error in result.errors)


def test_schema_validation_with_missing_indicator_description(sample_standard, sample_document_meta):
    """Test schema validation with missing standard.indicator.description."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["standard"]["indicator"]["description"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any(error.field_path == "standard.indicator.description" for error in result.errors)


def test_schema_validation_with_null_strand(sample_standard, sample_document_meta):
    """Test schema validation allows null strand."""
    # Create a standard without strand
    standard = NormalizedStandard(
        standard_id="US-CA-2021-LLD-1",
        country="US",
        state="CA",
        version_year=2021,
        domain=HierarchyLevel(code="LLD", name="Language and Literacy Development"),
        strand=None,
        sub_strand=None,
        indicator=HierarchyLevel(code="1", name="", description="Test indicator"),
        source_page=1,
        source_text="Test",
    )
    
    record = serialize_record(standard, sample_document_meta)
    result = validate_record(record)
    
    assert result.is_valid is True
    assert record["standard"]["strand"] is None
    assert record["standard"]["sub_strand"] is None


def test_serialization_round_trip_with_full_hierarchy(sample_standard, sample_document_meta):
    """Test serialization and deserialization round trip with full hierarchy."""
    # Serialize
    canonical = serialize_record(sample_standard, sample_document_meta)
    
    # Deserialize
    deserialized = deserialize_record(canonical)
    
    # Verify key fields
    assert deserialized.standard_id == sample_standard.standard_id
    assert deserialized.state == sample_standard.state
    assert deserialized.version_year == sample_standard.version_year
    assert deserialized.domain.code == sample_standard.domain.code
    assert deserialized.strand.code == sample_standard.strand.code
    assert deserialized.sub_strand.code == sample_standard.sub_strand.code
    assert deserialized.indicator.code == sample_standard.indicator.code


def test_serialization_round_trip_with_minimal_hierarchy(sample_document_meta):
    """Test serialization and deserialization with minimal hierarchy (2 levels)."""
    standard = NormalizedStandard(
        standard_id="US-TX-2020-MATH-1",
        country="US",
        state="TX",
        version_year=2020,
        domain=HierarchyLevel(code="MATH", name="Mathematics"),
        strand=None,
        sub_strand=None,
        indicator=HierarchyLevel(code="1", name="", description="Count to 10"),
        source_page=5,
        source_text="Test text",
    )
    
    canonical = serialize_record(standard, sample_document_meta)
    deserialized = deserialize_record(canonical)
    
    assert deserialized.standard_id == standard.standard_id
    assert deserialized.country == standard.country
    assert deserialized.strand is None
    assert deserialized.sub_strand is None


def test_standard_id_uniqueness_checking(sample_standard, sample_document_meta):
    """Test Standard_ID uniqueness checking."""
    record = serialize_record(sample_standard, sample_document_meta)
    
    # First validation without existing IDs - should pass
    result1 = validate_record(record, existing_ids=set())
    assert result1.is_valid is True
    
    # Second validation with the same ID in existing set - should fail
    existing_ids = {(
        sample_standard.country,
        sample_standard.state,
        sample_standard.version_year,
        sample_standard.standard_id
    )}
    result2 = validate_record(record, existing_ids=existing_ids)
    assert result2.is_valid is False
    assert any(error.error_type == "uniqueness" for error in result2.errors)


def test_s3_storage_of_validated_record(s3_client, sample_standard, sample_document_meta):
    """Test S3 storage of validated records."""
    record = serialize_record(sample_standard, sample_document_meta)
    
    # Store the record
    s3_key = store_validated_record(record, s3_client=s3_client)
    
    # Verify the S3 key format includes country
    expected_key = f"{sample_standard.country}/{sample_standard.state}/{sample_standard.version_year}/{sample_standard.standard_id}.json"
    assert s3_key == expected_key
    
    # Verify the record was stored
    response = s3_client.get_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=s3_key,
    )
    
    stored_data = json.loads(response["Body"].read())
    assert stored_data["country"] == sample_standard.country
    assert stored_data["state"] == sample_standard.state
    assert stored_data["standard"]["standard_id"] == sample_standard.standard_id


def test_multiple_validation_errors_collected(sample_standard, sample_document_meta):
    """Test that multiple validation errors are collected."""
    record = serialize_record(sample_standard, sample_document_meta)
    
    # Remove multiple required fields
    del record["country"]
    del record["state"]
    del record["document"]["title"]
    del record["standard"]["standard_id"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    assert len(result.errors) >= 4
    
    # Check that all errors are reported
    field_paths = {error.field_path for error in result.errors}
    assert "country" in field_paths
    assert "state" in field_paths
    assert "document.title" in field_paths
    assert "standard.standard_id" in field_paths


def test_validation_error_messages_are_descriptive(sample_standard, sample_document_meta):
    """Test that validation error messages are descriptive."""
    record = serialize_record(sample_standard, sample_document_meta)
    del record["state"]
    
    result = validate_record(record)
    
    assert result.is_valid is False
    state_error = next(e for e in result.errors if e.field_path == "state")
    assert "state" in state_error.message.lower()
    assert len(state_error.message) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
