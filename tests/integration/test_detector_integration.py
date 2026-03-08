"""Integration tests for structure detector with mocked Bedrock."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from els_pipeline.detector import (
    detect_structure,
    chunk_text_blocks,
    build_detection_prompt,
    parse_llm_response,
    call_bedrock_llm,
    estimate_tokens
)
from els_pipeline.models import TextBlock, DetectedElement, HierarchyLevelEnum


@pytest.fixture
def sample_text_blocks():
    """Create sample text blocks for testing."""
    return [
        TextBlock(
            text="Language and Literacy Development",
            page_number=1,
            block_type="LINE",
            confidence=0.99,
            geometry={"BoundingBox": {"Top": 0.1, "Left": 0.1}}
        ),
        TextBlock(
            text="LLD.A Listening and Speaking",
            page_number=1,
            block_type="LINE",
            confidence=0.98,
            geometry={"BoundingBox": {"Top": 0.2, "Left": 0.1}}
        ),
        TextBlock(
            text="LLD.A.1 Child demonstrates understanding of increasingly complex language.",
            page_number=1,
            block_type="LINE",
            confidence=0.97,
            geometry={"BoundingBox": {"Top": 0.3, "Left": 0.1}}
        )
    ]


@pytest.fixture
def mock_bedrock_response():
    """Create a mock Bedrock response."""
    return {
        'body': MagicMock(read=lambda: json.dumps({
            'content': [{
                'text': json.dumps([
                    {
                        "level": "domain",
                        "code": "LLD",
                        "title": "Language and Literacy Development",
                        "description": "Language and literacy skills",
                        "confidence": 0.95,
                        "source_page": 1,
                        "source_text": "Language and Literacy Development"
                    },
                    {
                        "level": "strand",
                        "code": "LLD.A",
                        "title": "Listening and Speaking",
                        "description": "Listening and speaking skills",
                        "confidence": 0.92,
                        "source_page": 1,
                        "source_text": "LLD.A Listening and Speaking"
                    },
                    {
                        "level": "indicator",
                        "code": "LLD.A.1",
                        "title": "Language Comprehension",
                        "description": "Child demonstrates understanding of increasingly complex language.",
                        "confidence": 0.88,
                        "source_page": 1,
                        "source_text": "LLD.A.1 Child demonstrates understanding of increasingly complex language."
                    }
                ])
            }]
        }).encode())
    }


def test_estimate_tokens():
    """Test token estimation."""
    text = "This is a test string"
    tokens = estimate_tokens(text)
    assert tokens > 0
    assert tokens == len(text) // 4


def test_chunk_text_blocks_empty():
    """Test chunking with empty blocks."""
    chunks = chunk_text_blocks([])
    assert chunks == []


def test_chunk_text_blocks_single_block(sample_text_blocks):
    """Test chunking with a single block."""
    single_block = [sample_text_blocks[0]]
    chunks = chunk_text_blocks(single_block, target_tokens=100)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1


def test_chunk_text_blocks_with_overlap():
    """Test chunking with overlap."""
    # Create blocks with known token counts
    blocks = [
        TextBlock(
            text="A" * 400,  # ~100 tokens
            page_number=1,
            block_type="LINE",
            confidence=0.99,
            geometry={"BoundingBox": {"Top": 0.1, "Left": 0.1}}
        )
        for _ in range(10)
    ]
    
    chunks = chunk_text_blocks(blocks, target_tokens=300, overlap_tokens=50)
    
    # Should create multiple chunks
    assert len(chunks) > 1
    
    # Each chunk should have blocks
    for chunk in chunks:
        assert len(chunk) > 0


def test_build_detection_prompt(sample_text_blocks):
    """Test prompt building."""
    prompt = build_detection_prompt(sample_text_blocks)
    
    assert "Language and Literacy Development" in prompt
    assert "[Page 1]" in prompt
    assert "JSON array" in prompt
    assert "domain" in prompt
    assert "indicator" in prompt


def test_parse_llm_response_valid(sample_text_blocks):
    """Test parsing valid LLM response."""
    response_text = json.dumps([
        {
            "level": "domain",
            "code": "LLD",
            "title": "Language and Literacy Development",
            "description": "Language skills",
            "confidence": 0.95,
            "source_page": 1,
            "source_text": "Language and Literacy Development"
        }
    ])
    
    elements = parse_llm_response(response_text, sample_text_blocks)
    
    assert len(elements) == 1
    assert elements[0].level == HierarchyLevelEnum.DOMAIN
    assert elements[0].code == "LLD"
    assert elements[0].confidence == 0.95


def test_parse_llm_response_with_extra_text(sample_text_blocks):
    """Test parsing LLM response with extra text around JSON."""
    response_text = """Here is the analysis:
    
    [
        {
            "level": "indicator",
            "code": "TEST.1",
            "title": "Test",
            "description": "Test description",
            "confidence": 0.85,
            "source_page": 1,
            "source_text": "Test text"
        }
    ]
    
    That's my analysis."""
    
    elements = parse_llm_response(response_text, sample_text_blocks)
    
    assert len(elements) == 1
    assert elements[0].code == "TEST.1"


def test_parse_llm_response_invalid_json(sample_text_blocks):
    """Test parsing invalid JSON response."""
    response_text = "This is not JSON"
    
    with pytest.raises(ValueError, match="No valid JSON array found"):
        parse_llm_response(response_text, sample_text_blocks)


def test_parse_llm_response_missing_fields(sample_text_blocks):
    """Test parsing response with missing required fields."""
    response_text = json.dumps([
        {
            "level": "domain",
            "code": "LLD"
            # Missing other required fields
        }
    ])
    
    elements = parse_llm_response(response_text, sample_text_blocks)
    
    # Should skip invalid elements
    assert len(elements) == 0


def test_parse_llm_response_invalid_level(sample_text_blocks):
    """Test parsing response with invalid level."""
    response_text = json.dumps([
        {
            "level": "invalid_level",
            "code": "TEST",
            "title": "Test",
            "description": "Test",
            "confidence": 0.9,
            "source_page": 1,
            "source_text": "Test"
        }
    ])
    
    elements = parse_llm_response(response_text, sample_text_blocks)
    
    # Should skip invalid elements
    assert len(elements) == 0


def test_parse_llm_response_confidence_clamping(sample_text_blocks):
    """Test that confidence values are clamped to [0.0, 1.0]."""
    response_text = json.dumps([
        {
            "level": "indicator",
            "code": "TEST.1",
            "title": "Test",
            "description": "Test",
            "confidence": 1.5,  # Out of range
            "source_page": 1,
            "source_text": "Test"
        }
    ])
    
    elements = parse_llm_response(response_text, sample_text_blocks)
    
    assert len(elements) == 1
    assert elements[0].confidence == 1.0  # Clamped to max


def test_confidence_threshold_flagging(sample_text_blocks):
    """Test confidence threshold flagging."""
    # High confidence element
    high_conf_response = json.dumps([
        {
            "level": "indicator",
            "code": "TEST.1",
            "title": "Test",
            "description": "Test",
            "confidence": 0.85,
            "source_page": 1,
            "source_text": "Test"
        }
    ])
    
    elements = parse_llm_response(high_conf_response, sample_text_blocks)
    assert elements[0].needs_review is False
    
    # Low confidence element
    low_conf_response = json.dumps([
        {
            "level": "indicator",
            "code": "TEST.2",
            "title": "Test",
            "description": "Test",
            "confidence": 0.65,
            "source_page": 1,
            "source_text": "Test"
        }
    ])
    
    elements = parse_llm_response(low_conf_response, sample_text_blocks)
    assert elements[0].needs_review is True


@patch('els_pipeline.detector.boto3.client')
def test_call_bedrock_llm_success(mock_boto_client, mock_bedrock_response):
    """Test successful Bedrock LLM call."""
    mock_client = Mock()
    mock_client.invoke_model.return_value = mock_bedrock_response
    mock_boto_client.return_value = mock_client
    
    response = call_bedrock_llm("Test prompt")
    
    assert response is not None
    assert isinstance(response, str)
    mock_client.invoke_model.assert_called_once()


@patch('els_pipeline.detector.boto3.client')
def test_call_bedrock_llm_retry(mock_boto_client):
    """Test Bedrock LLM call with retry."""
    mock_client = Mock()
    
    # First call fails, second succeeds
    mock_client.invoke_model.side_effect = [
        ClientError({'Error': {'Code': 'ThrottlingException'}}, 'InvokeModel'),
        {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Success'}]
            }).encode())
        }
    ]
    
    mock_boto_client.return_value = mock_client
    
    response = call_bedrock_llm("Test prompt", max_retries=2)
    
    assert response == 'Success'
    assert mock_client.invoke_model.call_count == 2


@patch('els_pipeline.detector.boto3.client')
def test_call_bedrock_llm_max_retries_exceeded(mock_boto_client):
    """Test Bedrock LLM call exceeding max retries."""
    mock_client = Mock()
    mock_client.invoke_model.side_effect = ClientError(
        {'Error': {'Code': 'ThrottlingException'}}, 'InvokeModel'
    )
    mock_boto_client.return_value = mock_client
    
    with pytest.raises(ClientError):
        call_bedrock_llm("Test prompt", max_retries=2)


@patch('els_pipeline.detector.call_bedrock_llm')
def test_detect_structure_success(mock_call_bedrock, sample_text_blocks):
    """Test successful structure detection."""
    mock_call_bedrock.return_value = json.dumps([
        {
            "level": "domain",
            "code": "LLD",
            "title": "Language and Literacy Development",
            "description": "Language skills",
            "confidence": 0.95,
            "source_page": 1,
            "source_text": "Language and Literacy Development"
        },
        {
            "level": "indicator",
            "code": "LLD.1",
            "title": "Test Indicator",
            "description": "Test description",
            "confidence": 0.65,  # Below threshold
            "source_page": 1,
            "source_text": "Test"
        }
    ])
    
    result = detect_structure(sample_text_blocks, "test-doc.pdf")
    
    assert result.status == "success"
    assert len(result.elements) == 2
    assert result.review_count == 1  # One element below threshold
    assert result.document_s3_key == "test-doc.pdf"


@patch('els_pipeline.detector.call_bedrock_llm')
def test_detect_structure_empty_blocks(mock_call_bedrock):
    """Test structure detection with empty blocks."""
    result = detect_structure([], "test-doc.pdf")
    
    assert result.status == "error"
    assert "No text blocks provided" in result.error
    assert len(result.elements) == 0


@patch('els_pipeline.detector.call_bedrock_llm')
def test_detect_structure_json_parse_retry(mock_call_bedrock, sample_text_blocks):
    """Test structure detection with JSON parsing retry."""
    # First two calls return invalid JSON, third succeeds
    mock_call_bedrock.side_effect = [
        "Invalid JSON",
        "Still invalid",
        json.dumps([
            {
                "level": "domain",
                "code": "TEST",
                "title": "Test",
                "description": "Test",
                "confidence": 0.9,
                "source_page": 1,
                "source_text": "Test"
            }
        ])
    ]
    
    result = detect_structure(sample_text_blocks, "test-doc.pdf")
    
    assert result.status == "success"
    assert len(result.elements) == 1


@patch('els_pipeline.detector.call_bedrock_llm')
def test_detect_structure_json_parse_failure(mock_call_bedrock, sample_text_blocks):
    """Test structure detection with persistent JSON parsing failure."""
    # All calls return invalid JSON
    mock_call_bedrock.return_value = "Invalid JSON"
    
    result = detect_structure(sample_text_blocks, "test-doc.pdf")
    
    # Should continue despite parse failures
    assert result.status == "success"
    assert len(result.elements) == 0  # No valid elements parsed


@patch('els_pipeline.detector.call_bedrock_llm')
def test_detect_structure_bedrock_exception(mock_call_bedrock, sample_text_blocks):
    """Test structure detection with Bedrock exception."""
    mock_call_bedrock.side_effect = Exception("Bedrock error")
    
    result = detect_structure(sample_text_blocks, "test-doc.pdf")
    
    assert result.status == "error"
    assert "Bedrock error" in result.error
