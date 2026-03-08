"""Integration tests for text extractor with mocked Textract."""

import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from els_pipeline.extractor import extract_text, _parse_textract_response, _sort_blocks_by_reading_order
from els_pipeline.models import TextBlock


@pytest.fixture
def mock_textract_response():
    """Mock Textract response with various block types."""
    return {
        'Blocks': [
            {
                'BlockType': 'LINE',
                'Text': 'Language and Literacy Development',
                'Page': 1,
                'Confidence': 99.5,
                'Geometry': {
                    'BoundingBox': {
                        'Top': 0.1,
                        'Left': 0.1,
                        'Width': 0.5,
                        'Height': 0.05
                    }
                }
            },
            {
                'BlockType': 'LINE',
                'Text': 'Domain: LLD',
                'Page': 1,
                'Confidence': 98.2,
                'Geometry': {
                    'BoundingBox': {
                        'Top': 0.2,
                        'Left': 0.1,
                        'Width': 0.3,
                        'Height': 0.04
                    }
                }
            },
            {
                'BlockType': 'CELL',
                'Text': 'Age Band',
                'Page': 1,
                'Confidence': 97.8,
                'RowIndex': 1,
                'ColumnIndex': 1,
                'Geometry': {
                    'BoundingBox': {
                        'Top': 0.3,
                        'Left': 0.1,
                        'Width': 0.2,
                        'Height': 0.03
                    }
                }
            },
            {
                'BlockType': 'CELL',
                'Text': '3-5 years',
                'Page': 1,
                'Confidence': 96.5,
                'RowIndex': 1,
                'ColumnIndex': 2,
                'Geometry': {
                    'BoundingBox': {
                        'Top': 0.3,
                        'Left': 0.3,
                        'Width': 0.2,
                        'Height': 0.03
                    }
                }
            },
            {
                'BlockType': 'LINE',
                'Text': 'Indicator 1.2',
                'Page': 2,
                'Confidence': 99.1,
                'Geometry': {
                    'BoundingBox': {
                        'Top': 0.05,
                        'Left': 0.1,
                        'Width': 0.3,
                        'Height': 0.04
                    }
                }
            }
        ]
    }


@pytest.fixture
def mock_empty_textract_response():
    """Mock empty Textract response."""
    return {'Blocks': []}


@pytest.fixture
def mock_textract_response_no_text():
    """Mock Textract response with blocks but no text."""
    return {
        'Blocks': [
            {
                'BlockType': 'PAGE',
                'Page': 1,
                'Geometry': {}
            }
        ]
    }


def test_successful_extraction_with_mocked_textract(mock_textract_response):
    """Test successful extraction with mocked Textract responses."""
    with patch('els_pipeline.extractor.boto3.client') as mock_boto_client:
        # Mock S3 client for head_object
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {'ContentLength': 1024 * 1024}  # 1MB
        
        # Mock Textract client - mock async methods since file is 1MB
        mock_textract = MagicMock()
        mock_textract.start_document_analysis.return_value = {'JobId': 'test-job-123'}
        mock_textract.get_document_analysis.return_value = {
            'JobStatus': 'SUCCEEDED',
            'Blocks': mock_textract_response['Blocks']
        }
        
        # Configure boto3.client to return appropriate mocks
        def client_side_effect(service, **kwargs):
            if service == 's3':
                return mock_s3
            elif service == 'textract':
                return mock_textract
            return MagicMock()
        
        mock_boto_client.side_effect = client_side_effect
        
        # Execute extraction
        result = extract_text('test/doc.pdf', 'version123')
        
        # Verify result
        assert result.status == 'success'
        assert result.error is None
        assert len(result.blocks) == 5
        assert result.total_pages == 2
        assert result.document_s3_key == 'test/doc.pdf'
        
        # Verify blocks are sorted by reading order
        assert result.blocks[0].page_number == 1
        assert result.blocks[-1].page_number == 2


def test_table_cell_parsing_and_structure_preservation(mock_textract_response):
    """Test table cell parsing and structure preservation."""
    blocks = _parse_textract_response(mock_textract_response)
    
    # Find table cell blocks
    table_cells = [b for b in blocks if b.block_type == 'TABLE_CELL']
    
    assert len(table_cells) == 2
    
    # Verify first cell
    assert table_cells[0].text == 'Age Band'
    assert table_cells[0].row_index == 0  # Converted from 1-based to 0-based
    assert table_cells[0].col_index == 0
    
    # Verify second cell
    assert table_cells[1].text == '3-5 years'
    assert table_cells[1].row_index == 0
    assert table_cells[1].col_index == 1


def test_reading_order_sorting():
    """Test reading order sorting."""
    blocks = [
        TextBlock(
            text='Page 2 top',
            page_number=2,
            block_type='LINE',
            confidence=0.99,
            geometry={'BoundingBox': {'Top': 0.1, 'Left': 0.1, 'Width': 0.3, 'Height': 0.05}}
        ),
        TextBlock(
            text='Page 1 bottom',
            page_number=1,
            block_type='LINE',
            confidence=0.99,
            geometry={'BoundingBox': {'Top': 0.9, 'Left': 0.1, 'Width': 0.3, 'Height': 0.05}}
        ),
        TextBlock(
            text='Page 1 top right',
            page_number=1,
            block_type='LINE',
            confidence=0.99,
            geometry={'BoundingBox': {'Top': 0.1, 'Left': 0.5, 'Width': 0.3, 'Height': 0.05}}
        ),
        TextBlock(
            text='Page 1 top left',
            page_number=1,
            block_type='LINE',
            confidence=0.99,
            geometry={'BoundingBox': {'Top': 0.1, 'Left': 0.1, 'Width': 0.3, 'Height': 0.05}}
        )
    ]
    
    sorted_blocks = _sort_blocks_by_reading_order(blocks)
    
    # Verify order: Page 1 top left, Page 1 top right, Page 1 bottom, Page 2 top
    assert sorted_blocks[0].text == 'Page 1 top left'
    assert sorted_blocks[1].text == 'Page 1 top right'
    assert sorted_blocks[2].text == 'Page 1 bottom'
    assert sorted_blocks[3].text == 'Page 2 top'


def test_error_handling_empty_response(mock_empty_textract_response):
    """Test error handling for empty Textract responses."""
    with patch('els_pipeline.extractor.boto3.client') as mock_boto_client:
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {'ContentLength': 1024 * 1024}
        
        # Mock Textract client with empty response
        mock_textract = MagicMock()
        mock_textract.start_document_analysis.return_value = {'JobId': 'test-job-empty'}
        mock_textract.get_document_analysis.return_value = {
            'JobStatus': 'SUCCEEDED',
            'Blocks': mock_empty_textract_response['Blocks']
        }
        
        def client_side_effect(service, **kwargs):
            if service == 's3':
                return mock_s3
            elif service == 'textract':
                return mock_textract
            return MagicMock()
        
        mock_boto_client.side_effect = client_side_effect
        
        # Execute extraction
        result = extract_text('test/empty.pdf', 'version123')
        
        # Verify error handling
        assert result.status == 'error'
        assert result.error == 'Empty extraction output'
        assert len(result.blocks) == 0


def test_error_handling_invalid_response(mock_textract_response_no_text):
    """Test error handling for invalid Textract responses (no text blocks)."""
    with patch('els_pipeline.extractor.boto3.client') as mock_boto_client:
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {'ContentLength': 1024 * 1024}
        
        # Mock Textract client with response containing no text
        mock_textract = MagicMock()
        mock_textract.start_document_analysis.return_value = {'JobId': 'test-job-notext'}
        mock_textract.get_document_analysis.return_value = {
            'JobStatus': 'SUCCEEDED',
            'Blocks': mock_textract_response_no_text['Blocks']
        }
        
        def client_side_effect(service, **kwargs):
            if service == 's3':
                return mock_s3
            elif service == 'textract':
                return mock_textract
            return MagicMock()
        
        mock_boto_client.side_effect = client_side_effect
        
        # Execute extraction
        result = extract_text('test/notext.pdf', 'version123')
        
        # Verify error handling
        assert result.status == 'error'
        assert result.error == 'Empty extraction output'


def test_error_handling_s3_access_failure():
    """Test error handling when S3 access fails."""
    with patch('els_pipeline.extractor.boto3.client') as mock_boto_client:
        # Mock S3 client that raises an error
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist'}},
            'HeadObject'
        )
        
        mock_boto_client.return_value = mock_s3
        
        # Execute extraction
        result = extract_text('test/missing.pdf', 'version123')
        
        # Verify error handling
        assert result.status == 'error'
        assert 'Failed to access document' in result.error


def test_error_handling_textract_failure():
    """Test error handling when Textract API fails."""
    with patch('els_pipeline.extractor.boto3.client') as mock_boto_client:
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {'ContentLength': 1024 * 1024}
        
        # Mock Textract client that raises an error
        mock_textract = MagicMock()
        mock_textract.start_document_analysis.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'StartDocumentAnalysis'
        )
        
        def client_side_effect(service, **kwargs):
            if service == 's3':
                return mock_s3
            elif service == 'textract':
                return mock_textract
            return MagicMock()
        
        mock_boto_client.side_effect = client_side_effect
        
        # Execute extraction
        result = extract_text('test/doc.pdf', 'version123')
        
        # Verify error handling
        assert result.status == 'error'
        assert result.error == 'Textract extraction failed'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
