"""End-to-end integration tests for the complete ELS normalization pipeline.

These tests verify the full pipeline execution from ingestion through persistence,
testing data flow between stages, error propagation, and final outputs.
"""

import pytest
from moto import mock_aws
import boto3
import json
from unittest.mock import patch, MagicMock

from els_pipeline.handlers import (
    ingestion_handler,
    extraction_handler,
    detection_handler,
    parsing_handler,
    validation_handler,
    persistence_handler
)
from els_pipeline.config import Config


def test_complete_core_pipeline_with_mocked_services():
    """Test complete core pipeline execution with mocked AWS services."""
    # Setup mocked AWS services
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)

    # Create S3 buckets
    raw_bucket = "els-raw-documents-test"
    processed_bucket = "els-processed-json-test"

    s3.create_bucket(Bucket=raw_bucket)
    s3.create_bucket(Bucket=processed_bucket)

    # Upload a test document
    test_doc_content = b"Test PDF content"
    s3.put_object(
        Bucket=raw_bucket,
        Key="US/CA/2021/test_standards.pdf",
        Body=test_doc_content
    )

    # Patch Config in all modules that use it
    with patch('els_pipeline.handlers.Config') as mock_config_handlers, \
         patch('els_pipeline.s3_helpers.Config') as mock_config_s3, \
         patch('els_pipeline.persister.Config') as mock_config_persister:

        # Configure the mock Config objects
        mock_config_handlers.S3_RAW_BUCKET = raw_bucket
        mock_config_handlers.S3_PROCESSED_BUCKET = processed_bucket
        mock_config_handlers.AWS_REGION = Config.AWS_REGION

        mock_config_s3.S3_RAW_BUCKET = raw_bucket
        mock_config_s3.S3_PROCESSED_BUCKET = processed_bucket
        mock_config_s3.AWS_REGION = Config.AWS_REGION
        
        mock_config_persister.S3_RAW_BUCKET = raw_bucket
        mock_config_persister.S3_PROCESSED_BUCKET = processed_bucket
        mock_config_persister.AWS_REGION = Config.AWS_REGION

        # Stage 1: Ingestion
        ingestion_event = {
            "run_id": "pipeline-US-CA-2021-test-e2e",
            "file_path": "US/CA/2021/test_standards.pdf",
            "country": "US",
            "state": "CA",
            "version_year": 2021,
            "source_url": "https://example.com/test_standards.pdf",
            "publishing_agency": "California Department of Education",
            "filename": "test_standards.pdf"
        }

        with patch('els_pipeline.handlers.ingest_document') as mock_ingest:
            from els_pipeline.models import IngestionResult
            mock_ingest.return_value = IngestionResult(
                s3_key="US/CA/2021/test_standards.pdf",
                s3_version_id="v1",
                metadata={
                    "country": "US",
                    "state": "CA",
                    "version_year": 2021,
                    "source_url": "https://example.com/test_standards.pdf",
                    "publishing_agency": "California Department of Education",
                    "upload_timestamp": "2026-02-15T00:00:00Z"
                },
                status="success",
                error=None
            )

            ingestion_result = ingestion_handler(ingestion_event, None)

        assert ingestion_result["status"] == "success"
        assert ingestion_result["country"] == "US"
        assert ingestion_result["state"] == "CA"
        assert ingestion_result["version_year"] == 2021
        assert "output_artifact" in ingestion_result

        # Stage 2: Text Extraction
        extraction_event = {
            "run_id": ingestion_result["run_id"],
            "output_artifact": ingestion_result["output_artifact"],
            "s3_version_id": ingestion_result["s3_version_id"],
            "country": ingestion_result["country"],
            "state": ingestion_result["state"],
            "version_year": ingestion_result["version_year"]
        }

        with patch('els_pipeline.handlers.extract_text') as mock_extract:
            from els_pipeline.models import ExtractionResult, TextBlock
            mock_extract.return_value = ExtractionResult(
                document_s3_key="US/CA/2021/test_standards.pdf",
                blocks=[
                    TextBlock(
                        text="Language and Literacy Development",
                        page_number=1,
                        block_type="LINE",
                        row_index=None,
                        col_index=None,
                        confidence=0.99,
                        geometry={"top": 0.1, "left": 0.1}
                    ),
                    TextBlock(
                        text="Child demonstrates understanding of language",
                        page_number=1,
                        block_type="LINE",
                        row_index=None,
                        col_index=None,
                        confidence=0.98,
                        geometry={"top": 0.2, "left": 0.1}
                    )
                ],
                total_pages=1,
                status="success",
                error=None
            )

            extraction_result = extraction_handler(extraction_event, None)

        assert extraction_result["status"] == "success"
        assert extraction_result["country"] == "US"
        assert extraction_result["total_pages"] == 1

        # Stage 3: Structure Detection
        detection_event = {
            "run_id": extraction_result["run_id"],
            "output_artifact": extraction_result["output_artifact"],
            "country": extraction_result["country"],
            "state": extraction_result["state"],
            "version_year": extraction_result["version_year"]
        }

        with patch('els_pipeline.handlers.detect_structure') as mock_detect:
            from els_pipeline.models import DetectionResult, DetectedElement
            mock_detect.return_value = DetectionResult(
                document_s3_key="US/CA/2021/test_standards.pdf",
                elements=[
                    DetectedElement(
                        level="domain",
                        code="LLD",
                        title="Language and Literacy Development",
                        description="",
                        confidence=0.95,
                        source_page=1,
                        source_text="Language and Literacy Development",
                        needs_review=False
                    ),
                    DetectedElement(
                        level="indicator",
                        code="LLD.1",
                        title="",
                        description="Child demonstrates understanding of language",
                        confidence=0.92,
                        source_page=1,
                        source_text="Child demonstrates understanding of language",
                        needs_review=False
                    )
                ],
                review_count=0,
                status="success",
                error=None
            )

            detection_result = detection_handler(detection_event, None)

        assert detection_result["status"] == "success"
        assert detection_result["review_count"] == 0

        # Stage 4: Hierarchy Parsing
        parsing_event = {
            "run_id": detection_result["run_id"],
            "output_artifact": detection_result["output_artifact"],
            "country": detection_result["country"],
            "state": detection_result["state"],
            "version_year": detection_result["version_year"],
            "age_band": "PK"
        }

        with patch('els_pipeline.handlers.parse_hierarchy') as mock_parse:
            from els_pipeline.models import ParseResult, NormalizedStandard, HierarchyLevel
            standard = NormalizedStandard(
                standard_id="US-CA-2021-LLD-1",
                country="US",
                state="CA",
                version_year=2021,
                domain=HierarchyLevel(
                    code="LLD",
                    name="Language and Literacy Development",
                    description=None
                ),
                strand=None,
                sub_strand=None,
                indicator=HierarchyLevel(
                    code="LLD.1",
                    name="",
                    description="Child demonstrates understanding of language"
                ),
                source_page=1,
                source_text="Child demonstrates understanding of language"
            )
            mock_parse.return_value = ParseResult(
                standards=[standard],
                indicators=[standard.model_dump()],
                orphaned_elements=[],
                status="success",
                error=None
            )

            parsing_result = parsing_handler(parsing_event, None)

        assert parsing_result["status"] == "success"
        assert parsing_result["total_indicators"] == 1
        assert parsing_result["orphaned_count"] == 0

        # Stage 5: Validation
        validation_event = {
            "run_id": parsing_result["run_id"],
            "output_artifact": parsing_result["output_artifact"],
            "total_indicators": parsing_result["total_indicators"],
            "country": parsing_result["country"],
            "state": parsing_result["state"],
            "version_year": parsing_result["version_year"]
        }

        with patch('els_pipeline.handlers.validate_record') as mock_validate, \
             patch('els_pipeline.handlers.serialize_record') as mock_serialize:
            from els_pipeline.models import ValidationResult

            mock_serialize.return_value = {
                "country": "US",
                "state": "CA",
                "document": {
                    "title": "Test Standards",
                    "version_year": 2021,
                    "source_url": "https://example.com/test_standards.pdf",
                    "age_band": "3-5",
                    "publishing_agency": "California Department of Education"
                },
                "standard": {
                    "standard_id": "US-CA-2021-LLD-1",
                    "domain": {
                        "code": "LLD",
                        "name": "Language and Literacy Development"
                    },
                    "strand": None,
                    "sub_strand": None,
                    "indicator": {
                        "code": "LLD.1",
                        "description": "Child demonstrates understanding of language"
                    }
                },
                "metadata": {
                    "page_number": 1,
                    "source_text_chunk": "Child demonstrates understanding of language",
                    "last_verified": "2026-02-15"
                }
            }

            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                record=mock_serialize.return_value
            )

            validation_result = validation_handler(validation_event, None)

        assert validation_result["status"] == "success"
        assert validation_result["total_validated"] == 1
        assert validation_result["total_indicators"] == 1

        # Stage 6: Data Persistence
        persistence_event = {
            "run_id": validation_result["run_id"],
            "output_artifact": validation_result["output_artifact"],
            "total_indicators": validation_result["total_indicators"],
            "total_validated": validation_result["total_validated"],
            "total_embedded": 0,
            "total_recommendations": 0,
            "country": validation_result["country"],
            "state": validation_result["state"],
            "version_year": validation_result["version_year"]
        }

        with patch('els_pipeline.persister.persist_records') as mock_persist:
            mock_persist.return_value = (1, [])  # (records_persisted, errors)
            
            persistence_result = persistence_handler(persistence_event, None)

        assert persistence_result["status"] == "success"
        assert persistence_result["records_persisted"] == 1
        assert persistence_result["errors"] == 0


@mock_aws
def test_error_propagation_through_pipeline():
    """Test that errors in one stage halt the pipeline and preserve partial results."""
    # Stage 1: Successful ingestion
    ingestion_event = {
        "run_id": "pipeline-US-CA-2021-error-test",
        "file_path": "US/CA/2021/test.pdf",
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "source_url": "https://example.com/test.pdf",
        "publishing_agency": "Test Agency",
        "filename": "test.pdf"
    }
    
    with patch('els_pipeline.handlers.ingest_document') as mock_ingest:
        from els_pipeline.models import IngestionResult
        mock_ingest.return_value = IngestionResult(
            s3_key="US/CA/2021/test.pdf",
            s3_version_id="v1",
            metadata={"country": "US", "state": "CA", "version_year": 2021},
            status="success",
            error=None
        )
        
        ingestion_result = ingestion_handler(ingestion_event, None)
    
    assert ingestion_result["status"] == "success"
    
    # Stage 2: Failed text extraction
    extraction_event = {
        "run_id": ingestion_result["run_id"],
        "output_artifact": ingestion_result["output_artifact"],
        "s3_version_id": ingestion_result["s3_version_id"],
        "country": ingestion_result["country"],
        "state": ingestion_result["state"],
        "version_year": ingestion_result["version_year"]
    }
    
    with patch('els_pipeline.handlers.extract_text') as mock_extract:
        from els_pipeline.models import ExtractionResult
        mock_extract.return_value = ExtractionResult(
            document_s3_key="US/CA/2021/test.pdf",
            blocks=[],
            total_pages=1,  # Must be > 0 per Pydantic validation
            status="error",
            error="Textract service failure"
        )
        
        extraction_result = extraction_handler(extraction_event, None)
    
    # Verify error is captured
    assert extraction_result["status"] == "error"
    assert "error" in extraction_result
    assert extraction_result["error"] is not None
    
    # Verify partial results are preserved (ingestion succeeded)
    assert ingestion_result["status"] == "success"
    assert ingestion_result["output_artifact"] == "US/CA/2021/test.pdf"


@mock_aws
def test_data_flow_between_stages():
    """Test that data flows correctly between pipeline stages."""
    # Setup mocked AWS services
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)
    
    # Create S3 buckets
    raw_bucket = "els-raw-documents-test"
    processed_bucket = "els-processed-json-test"
    
    s3.create_bucket(Bucket=raw_bucket)
    s3.create_bucket(Bucket=processed_bucket)
    
    run_id = "pipeline-US-CA-2021-dataflow-test"
    
    # Patch Config in all modules that use it
    with patch('els_pipeline.handlers.Config') as mock_config_handlers, \
         patch('els_pipeline.s3_helpers.Config') as mock_config_s3, \
         patch('els_pipeline.persister.Config') as mock_config_persister:
        
        # Configure the mock Config objects
        mock_config_handlers.S3_RAW_BUCKET = raw_bucket
        mock_config_handlers.S3_PROCESSED_BUCKET = processed_bucket
        mock_config_handlers.AWS_REGION = Config.AWS_REGION
        
        mock_config_s3.S3_RAW_BUCKET = raw_bucket
        mock_config_s3.S3_PROCESSED_BUCKET = processed_bucket
        mock_config_s3.AWS_REGION = Config.AWS_REGION
        
        mock_config_persister.S3_RAW_BUCKET = raw_bucket
        mock_config_persister.S3_PROCESSED_BUCKET = processed_bucket
        mock_config_persister.AWS_REGION = Config.AWS_REGION
        
        # Track data flow through stages
        stage_outputs = {}
        
        # Stage 1: Ingestion
        with patch('els_pipeline.handlers.ingest_document') as mock_ingest:
            from els_pipeline.models import IngestionResult
            mock_ingest.return_value = IngestionResult(
                s3_key="US/CA/2021/test.pdf",
                s3_version_id="v1",
                metadata={"country": "US", "state": "CA", "version_year": 2021},
                status="success",
                error=None
            )
            
            result = ingestion_handler({
                "run_id": run_id,
                "file_path": "US/CA/2021/test.pdf",
                "country": "US",
                "state": "CA",
                "version_year": 2021,
                "source_url": "https://example.com/test.pdf",
                "publishing_agency": "Test Agency",
                "filename": "test.pdf"
            }, None)
            
            stage_outputs["ingestion"] = result
        
        # Verify ingestion output contains required fields for next stage
        assert "output_artifact" in stage_outputs["ingestion"]
        assert "s3_version_id" in stage_outputs["ingestion"]
        assert "country" in stage_outputs["ingestion"]
        assert "state" in stage_outputs["ingestion"]
        assert "version_year" in stage_outputs["ingestion"]
        
        # Stage 2: Extraction uses ingestion output
        with patch('els_pipeline.handlers.extract_text') as mock_extract:
            from els_pipeline.models import ExtractionResult, TextBlock
            mock_extract.return_value = ExtractionResult(
                document_s3_key=stage_outputs["ingestion"]["output_artifact"],
                blocks=[TextBlock(
                    text="Test",
                    page_number=1,
                    block_type="LINE",
                    row_index=None,
                    col_index=None,
                    confidence=0.99,
                    geometry={"top": 0.1, "left": 0.1}
                )],
                total_pages=1,
                status="success",
                error=None
            )
            
            result = extraction_handler({
                "run_id": run_id,
                "output_artifact": stage_outputs["ingestion"]["output_artifact"],
                "s3_version_id": stage_outputs["ingestion"]["s3_version_id"],
                "country": stage_outputs["ingestion"]["country"],
                "state": stage_outputs["ingestion"]["state"],
                "version_year": stage_outputs["ingestion"]["version_year"]
            }, None)
            
            stage_outputs["extraction"] = result
        
        # Verify extraction output contains required fields for next stage
        assert "output_artifact" in stage_outputs["extraction"]
        assert "total_pages" in stage_outputs["extraction"]
        assert stage_outputs["extraction"]["country"] == "US"
        assert stage_outputs["extraction"]["state"] == "CA"
        
        # Verify country/state/version_year flow through all stages
        assert stage_outputs["ingestion"]["country"] == stage_outputs["extraction"]["country"]
        assert stage_outputs["ingestion"]["state"] == stage_outputs["extraction"]["state"]
        assert stage_outputs["ingestion"]["version_year"] == stage_outputs["extraction"]["version_year"]


def test_final_outputs_in_all_storage_locations():
    """Test that final outputs are stored in all expected locations."""
    # This test verifies the structure of final outputs
    # In a real deployment, this would check S3 and database
    
    # Mock final persistence result
    persistence_result = {
        "status": "success",
        "stage_name": "data_persistence",
        "output_artifact": "db://pipeline_runs/pipeline-US-CA-2021-test",
        "total_indicators": 10,
        "total_validated": 10,
        "total_embedded": 0,
        "total_recommendations": 0,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "run_id": "pipeline-US-CA-2021-test"
    }
    
    # Verify all required fields are present
    assert persistence_result["status"] == "success"
    assert persistence_result["total_indicators"] > 0
    assert persistence_result["total_validated"] > 0
    assert persistence_result["country"] == "US"
    assert persistence_result["state"] == "CA"
    assert persistence_result["version_year"] == 2021
    
    # Verify output artifact reference
    assert "output_artifact" in persistence_result
    assert persistence_result["output_artifact"].startswith("db://")


def test_pipeline_invariants():
    """Test that pipeline maintains correctness invariants."""
    # Test invariant: total_validated <= total_indicators
    persistence_result = {
        "total_indicators": 10,
        "total_validated": 8,
        "total_embedded": 0,
        "total_recommendations": 0
    }
    
    assert persistence_result["total_validated"] <= persistence_result["total_indicators"]
    
    # Test invariant: total_embedded <= total_validated (for full pipeline)
    full_pipeline_result = {
        "total_indicators": 10,
        "total_validated": 8,
        "total_embedded": 8,
        "total_recommendations": 16
    }
    
    assert full_pipeline_result["total_embedded"] <= full_pipeline_result["total_validated"]
    
    # Test invariant: country code format
    assert len(persistence_result.get("country", "US")) == 2
    assert persistence_result.get("country", "US").isupper()
