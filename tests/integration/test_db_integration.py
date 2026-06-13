"""Integration tests for database access layer.

These tests verify the database operations work correctly with a test database.
For local testing, they use mocked connections. For AWS testing, use the manual test script.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from els_pipeline.db import (
    DatabaseConnection,
    persist_standard,
    get_indicators_by_country_state
)
from els_pipeline.models import (
    NormalizedStandard,
    HierarchyLevel
)


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection for integration tests."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn, cursor


@pytest.fixture
def sample_standards():
    """Create sample standards for testing."""
    return [
        NormalizedStandard(
            standard_id="US-CA-2021-LLD-1.2",
            country="US",
            state="CA",
            version_year=2021,
            domain=HierarchyLevel(code="LLD", name="Language and Literacy Development"),
            strand=HierarchyLevel(code="LLD.A", name="Listening and Speaking"),
            sub_strand=None,
            indicator=HierarchyLevel(
                code="LLD.A.1.a",
                name="Indicator 1.2",
                description="Child demonstrates understanding of increasingly complex language."
            ),
            source_page=43,
            source_text="Sample source text"
        ),
        NormalizedStandard(
            standard_id="US-TX-2022-MTH-1",
            country="US",
            state="TX",
            version_year=2022,
            domain=HierarchyLevel(code="MTH", name="Mathematics"),
            strand=None,
            sub_strand=None,
            indicator=HierarchyLevel(code="MTH.1", name="Indicator 1", description="Count to 10"),
            source_page=1,
            source_text="Sample"
        )
    ]


class TestDatabaseConnectionPooling:
    """Test database connection pooling functionality."""
    
    def test_connection_pool_initialization(self):
        """Test that connection pool initializes correctly."""
        with patch('els_pipeline.db.SimpleConnectionPool') as mock_pool:
            DatabaseConnection._pool = None
            DatabaseConnection.initialize_pool(
                host='testhost',
                port=5432,
                database='testdb',
                user='testuser',
                password='testpass',
                minconn=2,
                maxconn=10
            )
            
            mock_pool.assert_called_once()
            call_kwargs = mock_pool.call_args[1]
            assert call_kwargs['host'] == 'testhost'
            assert call_kwargs['minconn'] == 2
            assert call_kwargs['maxconn'] == 10
    
    def test_connection_pool_reuse(self):
        """Test that connection pool is reused if already initialized."""
        with patch('els_pipeline.db.SimpleConnectionPool') as mock_pool:
            DatabaseConnection._pool = MagicMock()
            DatabaseConnection.initialize_pool()
            
            # Should not create a new pool
            mock_pool.assert_not_called()


class TestStandardPersistence:
    """Test persisting standards to the database."""
    
    def test_persist_multiple_standards(self, mock_db_connection, sample_standards):
        """Test persisting multiple standards in sequence."""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [(1,), (2,), (3,), (4,), (5,), (6,)]
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            document_meta = {
                'title': 'Test Standards',
                'source_url': 'https://example.com',
                'age_band': '3-5',
                'publishing_agency': 'Test Agency'
            }
            
            # Persist both standards
            for standard in sample_standards:
                persist_standard(standard, document_meta)
            
            # Verify both were committed
            assert conn.commit.call_count == 2
    
    def test_persist_standard_with_full_hierarchy(self, mock_db_connection):
        """Test persisting a standard with all four hierarchy levels."""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [(1,), (2,), (3,), (4,)]
        
        standard = NormalizedStandard(
            standard_id="US-CA-2021-LLD-1.2.3.a",
            country="US",
            state="CA",
            version_year=2021,
            domain=HierarchyLevel(code="LLD", name="Language and Literacy Development"),
            strand=HierarchyLevel(code="LLD.A", name="Listening and Speaking"),
            sub_strand=HierarchyLevel(code="LLD.A.1", name="Comprehension"),
            indicator=HierarchyLevel(
                code="LLD.A.1.a",
                name="Indicator",
                description="Test description"
            ),
            source_page=1,
            source_text="Test"
        )
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            document_meta = {
                'title': 'Test',
                'source_url': 'https://example.com',
                'age_band': '3-5',
                'publishing_agency': 'Test'
            }
            
            persist_standard(standard, document_meta)
            
            # Should insert document, domain, strand, sub_strand, and indicator
            assert cursor.execute.call_count >= 5
            conn.commit.assert_called_once()


class TestIndicatorRetrieval:
    """Test retrieving indicators by country and state."""
    
    def test_get_indicators_by_country_state_basic(self, mock_db_connection):
        """Test basic indicator retrieval by country and state."""
        conn, cursor = mock_db_connection
        
        mock_results = [
            {
                'standard_id': 'US-CA-2021-LLD-1',
                'indicator_code': 'LLD.1',
                'description': 'Test 1',
                'domain_code': 'LLD',
                'domain_name': 'Language',
                'strand_code': None,
                'strand_name': None,
                'sub_strand_code': None,
                'sub_strand_name': None,
                'country': 'US',
                'state': 'CA',
                'age_band': '3-5',
                'version_year': 2021,
                'source_page': 1
            },
            {
                'standard_id': 'US-CA-2021-MTH-1',
                'indicator_code': 'MTH.1',
                'description': 'Test 2',
                'domain_code': 'MTH',
                'domain_name': 'Mathematics',
                'strand_code': None,
                'strand_name': None,
                'sub_strand_code': None,
                'sub_strand_name': None,
                'country': 'US',
                'state': 'CA',
                'age_band': '3-5',
                'version_year': 2021,
                'source_page': 2
            }
        ]
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            cursor.fetchall.return_value = mock_results
            
            results = get_indicators_by_country_state('US', 'CA')
            
            assert len(results) == 2
            assert all(r['country'] == 'US' for r in results)
            assert all(r['state'] == 'CA' for r in results)
    
    def test_get_indicators_with_domain_filter(self, mock_db_connection):
        """Test indicator retrieval filtered by domain."""
        conn, cursor = mock_db_connection
        
        mock_results = [
            {
                'standard_id': 'US-CA-2021-LLD-1',
                'indicator_code': 'LLD.1',
                'description': 'Test',
                'domain_code': 'LLD',
                'domain_name': 'Language',
                'strand_code': None,
                'strand_name': None,
                'sub_strand_code': None,
                'sub_strand_name': None,
                'country': 'US',
                'state': 'CA',
                'age_band': '3-5',
                'version_year': 2021,
                'source_page': 1
            }
        ]
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            cursor.fetchall.return_value = mock_results
            
            results = get_indicators_by_country_state('US', 'CA', domain_code='LLD')
            
            # Verify domain filter was applied
            cursor.execute.assert_called_once()
            query_sql = cursor.execute.call_args[0][0]
            assert 'dom.code = %s' in query_sql
            
            assert len(results) == 1
            assert results[0]['domain_code'] == 'LLD'
    
    def test_get_indicators_with_strand_filter(self, mock_db_connection):
        """Test indicator retrieval filtered by strand."""
        conn, cursor = mock_db_connection
        
        mock_results = [
            {
                'standard_id': 'US-CA-2021-LLD-1',
                'indicator_code': 'LLD.A.1',
                'description': 'Test',
                'domain_code': 'LLD',
                'domain_name': 'Language',
                'strand_code': 'LLD.A',
                'strand_name': 'Listening',
                'sub_strand_code': None,
                'sub_strand_name': None,
                'country': 'US',
                'state': 'CA',
                'age_band': '3-5',
                'version_year': 2021,
                'source_page': 1
            }
        ]
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            cursor.fetchall.return_value = mock_results
            
            results = get_indicators_by_country_state('US', 'CA', strand_code='LLD.A')
            
            # Verify strand filter was applied
            cursor.execute.assert_called_once()
            query_sql = cursor.execute.call_args[0][0]
            assert 'str.code = %s' in query_sql
            
            assert len(results) == 1
            assert results[0]['strand_code'] == 'LLD.A'


class TestErrorHandling:
    """Test error handling in database operations."""
    
    def test_persist_standard_rollback_on_error(self, mock_db_connection, sample_standards):
        """Test that transaction is rolled back on error."""
        conn, cursor = mock_db_connection
        cursor.execute.side_effect = Exception("Database error")
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            document_meta = {
                'title': 'Test',
                'source_url': 'https://example.com',
                'age_band': '3-5',
                'publishing_agency': 'Test'
            }
            
            with pytest.raises(Exception):
                persist_standard(sample_standards[0], document_meta)
            
            # Verify rollback was called
            conn.rollback.assert_called_once()
            conn.commit.assert_not_called()
