"""Property tests for document ingestion.

Feature: els-normalization-pipeline
Property 2: Ingestion Metadata Completeness
Property 3: Format Validation Correctness
"""

import tempfile
import os
from pathlib import Path
from hypothesis import given, strategies as st, assume
from unittest.mock import patch, MagicMock

from els_pipeline.ingester import ingest_document, validate_format, SUPPORTED_FORMATS
from els_pipeline.models import IngestionRequest


# Strategy for generating country codes (ISO 3166-1 alpha-2)
country_code_strategy = st.text(
    alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    min_size=2,
    max_size=2
)

# Strategy for generating state codes
state_code_strategy = st.text(
    alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    min_size=2,
    max_size=2
)

# Strategy for generating version years
year_strategy = st.integers(min_value=2000, max_value=2030)

# Strategy for generating URLs
url_strategy = st.text(min_size=10, max_size=100).map(lambda x: f"https://example.com/{x}")

# Strategy for generating agency names
agency_strategy = st.text(min_size=5, max_size=100)

# Strategy for generating supported file extensions
supported_ext_strategy = st.sampled_from(list(SUPPORTED_FORMATS))

# Strategy for generating unsupported file extensions
unsupported_ext_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
    min_size=2,
    max_size=5
).map(lambda x: f".{x}").filter(lambda x: x not in SUPPORTED_FORMATS)


@given(
    country=country_code_strategy,
    state=state_code_strategy,
    year=year_strategy,
    source_url=url_strategy,
    agency=agency_strategy,
    ext=supported_ext_strategy
)
def test_property_2_ingestion_metadata_completeness(
    country: str,
    state: str,
    year: int,
    source_url: str,
    agency: str,
    ext: str
):
    """
    Property 2: Ingestion Metadata Completeness
    
    For any successful ingestion result, the metadata dictionary SHALL contain
    non-empty values for all required keys: country, state, version_year, source_url,
    publishing_agency, and upload_timestamp.
    
    Validates: Requirements 1.2
    """
    # Create a temporary file with supported extension
    with tempfile.NamedTemporaryFile(mode="wb", suffix=ext, delete=False) as tmp_file:
        tmp_file.write(b"Test document content")
        tmp_path = tmp_file.name
    
    try:
        filename = f"test_doc{ext}"
        
        # Create ingestion request
        request = IngestionRequest(
            file_path=tmp_path,
            country=country,
            state=state,
            version_year=year,
            source_url=source_url,
            publishing_agency=agency,
            filename=filename
        )
        
        # Mock S3 client to avoid actual AWS calls
        with patch("els_pipeline.ingester.boto3.client") as mock_boto3:
            mock_s3 = MagicMock()
            mock_s3.put_object.return_value = {"VersionId": "test-version-123"}
            mock_boto3.return_value = mock_s3
            
            # Perform ingestion
            result = ingest_document(request)
            
            # Only check metadata completeness for successful ingestions
            if result.status == "success":
                # Assert all required metadata keys are present
                required_keys = {"country", "state", "version_year", "source_url", "publishing_agency", "upload_timestamp"}
                assert required_keys.issubset(result.metadata.keys()), \
                    f"Missing required metadata keys: {required_keys - result.metadata.keys()}"
                
                # Assert all metadata values are non-empty
                for key in required_keys:
                    value = result.metadata[key]
                    assert value is not None, f"Metadata key '{key}' should not be None"
                    assert str(value).strip() != "", f"Metadata key '{key}' should not be empty"
                
                # Assert specific values match the request
                assert result.metadata["country"] == country
                assert result.metadata["state"] == state
                assert result.metadata["version_year"] == str(year)
                assert result.metadata["source_url"] == source_url
                assert result.metadata["publishing_agency"] == agency
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@given(ext=supported_ext_strategy)
def test_property_3_format_validation_accepts_supported(ext: str):
    """
    Property 3: Format Validation Correctness (Part 1)
    
    For any file with extension in {".pdf", ".html"}, the format validator
    SHALL accept it.
    
    Validates: Requirements 1.4
    """
    filename = f"document{ext}"
    is_valid, error_msg = validate_format(filename)
    
    assert is_valid is True, f"Supported format {ext} should be accepted"
    assert error_msg is None, f"Supported format {ext} should not produce an error message"


@given(ext=unsupported_ext_strategy)
def test_property_3_format_validation_rejects_unsupported(ext: str):
    """
    Property 3: Format Validation Correctness (Part 2)
    
    For any file with an extension outside {".pdf", ".html"}, the format
    validator SHALL reject it with a non-empty error message.
    
    Validates: Requirements 1.4
    """
    # Ensure the extension is truly unsupported
    assume(ext.lower() not in SUPPORTED_FORMATS)
    
    filename = f"document{ext}"
    is_valid, error_msg = validate_format(filename)
    
    assert is_valid is False, f"Unsupported format {ext} should be rejected"
    assert error_msg is not None, f"Unsupported format {ext} should produce an error message"
    assert len(error_msg) > 0, f"Error message should not be empty for unsupported format {ext}"
    # Check case-insensitively since the error message uses lowercase
    assert ext.lower() in error_msg.lower(), f"Error message should mention the rejected extension {ext}"
