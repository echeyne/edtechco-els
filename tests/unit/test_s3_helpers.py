"""Unit tests for S3 helper functions."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from els_pipeline.s3_helpers import (
    save_json_to_s3,
    load_json_from_s3,
    construct_intermediate_key
)


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    with patch('els_pipeline.s3_helpers.boto3.client') as mock_client:
        client = MagicMock()
        mock_client.return_value = client
        yield client


@pytest.fixture
def sample_data():
    """Create sample JSON data for testing."""
    return {
        "blocks": [
            {"id": "1", "text": "Sample text", "confidence": 0.95},
            {"id": "2", "text": "Another block", "confidence": 0.98}
        ],
        "total_pages": 5,
        "total_blocks": 2,
        "extraction_timestamp": "2024-01-15T10:30:00Z"
    }


class TestSaveJsonToS3:
    """Tests for save_json_to_s3 function."""
    
    def test_save_json_success(self, mock_s3_client, sample_data):
        """Test successfully saving JSON to S3."""
        bucket = "test-bucket"
        key = "test/path/data.json"
        
        save_json_to_s3(sample_data, bucket, key)
        
        # Verify S3 client was called correctly
        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        
        assert call_kwargs['Bucket'] == bucket
        assert call_kwargs['Key'] == key
        assert call_kwargs['ContentType'] == 'application/json'
        
        # Verify JSON was serialized correctly
        body = call_kwargs['Body']
        parsed = json.loads(body)
        assert parsed == sample_data
        assert '"blocks"' in body  # Check formatting with indent
    
    def test_save_json_with_empty_dict(self, mock_s3_client):
        """Test saving an empty dictionary."""
        bucket = "test-bucket"
        key = "empty.json"
        
        save_json_to_s3({}, bucket, key)
        
        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs['Body'] == '{}'
    
    def test_save_json_access_denied_error(self, mock_s3_client):
        """Test handling AccessDenied error."""
        mock_s3_client.put_object.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'AccessDenied',
                    'Message': 'Access Denied'
                }
            },
            'PutObject'
        )
        
        bucket = "test-bucket"
        key = "test.json"
        
        with pytest.raises(ClientError) as exc_info:
            save_json_to_s3({"test": "data"}, bucket, key)
        
        error = exc_info.value
        assert error.response['Error']['Code'] == 'AccessDenied'
        assert 'IAM permissions may need to be updated' in error.response['Error']['Message']
        assert bucket in error.response['Error']['Message']
        assert key in error.response['Error']['Message']
    
    def test_save_json_generic_error(self, mock_s3_client):
        """Test handling generic S3 errors."""
        mock_s3_client.put_object.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'InternalError',
                    'Message': 'Internal Server Error'
                }
            },
            'PutObject'
        )
        
        with pytest.raises(ClientError) as exc_info:
            save_json_to_s3({"test": "data"}, "bucket", "key")
        
        assert exc_info.value.response['Error']['Code'] == 'InternalError'


class TestLoadJsonFromS3:
    """Tests for load_json_from_s3 function."""
    
    def test_load_json_success(self, mock_s3_client, sample_data):
        """Test successfully loading JSON from S3."""
        bucket = "test-bucket"
        key = "test/path/data.json"
        
        # Mock S3 response
        json_bytes = json.dumps(sample_data).encode('utf-8')
        mock_body = MagicMock()
        mock_body.read.return_value = json_bytes
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        result = load_json_from_s3(bucket, key)
        
        # Verify S3 client was called correctly
        mock_s3_client.get_object.assert_called_once_with(Bucket=bucket, Key=key)
        
        # Verify data was deserialized correctly
        assert result == sample_data
        assert result['total_pages'] == 5
        assert len(result['blocks']) == 2
    
    def test_load_json_empty_object(self, mock_s3_client):
        """Test loading an empty JSON object."""
        bucket = "test-bucket"
        key = "empty.json"
        
        mock_body = MagicMock()
        mock_body.read.return_value = b'{}'
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        result = load_json_from_s3(bucket, key)
        
        assert result == {}
    
    def test_load_json_no_such_key_error(self, mock_s3_client):
        """Test handling NoSuchKey error."""
        mock_s3_client.get_object.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'NoSuchKey',
                    'Message': 'The specified key does not exist'
                }
            },
            'GetObject'
        )
        
        bucket = "test-bucket"
        key = "missing.json"
        
        with pytest.raises(ClientError) as exc_info:
            load_json_from_s3(bucket, key)
        
        error = exc_info.value
        assert error.response['Error']['Code'] == 'NoSuchKey'
        assert 'Expected intermediate data was not found' in error.response['Error']['Message']
        assert f"s3://{bucket}/{key}" in error.response['Error']['Message']
    
    def test_load_json_access_denied_error(self, mock_s3_client):
        """Test handling AccessDenied error."""
        mock_s3_client.get_object.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'AccessDenied',
                    'Message': 'Access Denied'
                }
            },
            'GetObject'
        )
        
        bucket = "test-bucket"
        key = "test.json"
        
        with pytest.raises(ClientError) as exc_info:
            load_json_from_s3(bucket, key)
        
        error = exc_info.value
        assert error.response['Error']['Code'] == 'AccessDenied'
        assert 'IAM permissions may need to be updated' in error.response['Error']['Message']
        assert bucket in error.response['Error']['Message']
        assert key in error.response['Error']['Message']
    
    def test_load_json_generic_error(self, mock_s3_client):
        """Test handling generic S3 errors."""
        mock_s3_client.get_object.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'InternalError',
                    'Message': 'Internal Server Error'
                }
            },
            'GetObject'
        )
        
        with pytest.raises(ClientError) as exc_info:
            load_json_from_s3("bucket", "key")
        
        assert exc_info.value.response['Error']['Code'] == 'InternalError'
    
    def test_load_json_invalid_json(self, mock_s3_client):
        """Test handling invalid JSON data."""
        bucket = "test-bucket"
        key = "invalid.json"
        
        mock_body = MagicMock()
        mock_body.read.return_value = b'not valid json{'
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        with pytest.raises(json.JSONDecodeError):
            load_json_from_s3(bucket, key)


class TestConstructIntermediateKey:
    """Tests for construct_intermediate_key function."""
    
    def test_construct_key_extraction_stage(self):
        """Test constructing key for extraction stage."""
        key = construct_intermediate_key(
            country="US",
            state="CA",
            year=2021,
            stage="extraction",
            run_id="run-12345"
        )
        
        assert key == "US/CA/2021/intermediate/extraction/run-12345.json"
    
    def test_construct_key_detection_stage(self):
        """Test constructing key for detection stage."""
        key = construct_intermediate_key(
            country="US",
            state="TX",
            year=2022,
            stage="detection",
            run_id="run-67890"
        )
        
        assert key == "US/TX/2022/intermediate/detection/run-67890.json"
    
    def test_construct_key_parsing_stage(self):
        """Test constructing key for parsing stage."""
        key = construct_intermediate_key(
            country="US",
            state="NY",
            year=2023,
            stage="parsing",
            run_id="run-abc123"
        )
        
        assert key == "US/NY/2023/intermediate/parsing/run-abc123.json"
    
    def test_construct_key_validation_stage(self):
        """Test constructing key for validation stage."""
        key = construct_intermediate_key(
            country="US",
            state="FL",
            year=2020,
            stage="validation",
            run_id="run-xyz789"
        )
        
        assert key == "US/FL/2020/intermediate/validation/run-xyz789.json"
    
    def test_construct_key_with_special_characters(self):
        """Test constructing key with special characters in run_id."""
        key = construct_intermediate_key(
            country="US",
            state="CA",
            year=2021,
            stage="extraction",
            run_id="run-2024-01-15T10:30:00Z"
        )
        
        assert key == "US/CA/2021/intermediate/extraction/run-2024-01-15T10:30:00Z.json"
    
    def test_construct_key_pattern_consistency(self):
        """Test that all keys follow the same pattern."""
        stages = ["extraction", "detection", "parsing", "validation"]
        
        for stage in stages:
            key = construct_intermediate_key(
                country="US",
                state="CA",
                year=2021,
                stage=stage,
                run_id="test-run"
            )
            
            # Verify pattern
            assert key.startswith("US/CA/2021/intermediate/")
            assert key.endswith(".json")
            assert f"/{stage}/" in key
            assert "test-run" in key
