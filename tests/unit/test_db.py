"""Unit tests for database access layer."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from els_pipeline.db import (
    DatabaseConnection,
    persist_standard,
    persist_embedding,
    persist_recommendation,
    query_similar_indicators,
    get_indicators_by_country_state
)
from els_pipeline.models import (
    NormalizedStandard,
    HierarchyLevel,
    EmbeddingRecord,
    Recommendation,
    AudienceEnum
)


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn, cursor


@pytest.fixture
def sample_standard():
    """Create a sample normalized standard."""
    return NormalizedStandard(
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
    )


@pytest.fixture
def sample_embedding():
    """Create a sample embedding record."""
    return EmbeddingRecord(
        indicator_id="US-CA-2021-LLD-1.2",
        country="US",
        state="CA",
        vector=[0.1] * 1536,
        embedding_model="amazon.titan-embed-text-v1",
        embedding_version="v1",
        input_text="Language and Literacy Development – Listening and Speaking – Child demonstrates understanding",
        created_at=datetime.now().isoformat()
    )


@pytest.fixture
def sample_recommendation():
    """Create a sample recommendation."""
    return Recommendation(
        recommendation_id="rec-001",
        indicator_id="US-CA-2021-LLD-1.2",
        country="US",
        state="CA",
        audience=AudienceEnum.PARENT,
        activity_description="Read picture books together and ask open-ended questions",
        age_band="3-5",
        generation_model="anthropic.claude-v2",
        created_at=datetime.now().isoformat()
    )


class TestDatabaseConnection:
    """Tests for DatabaseConnection class."""
    
    def test_initialize_pool(self):
        """Test connection pool initialization."""
        with patch('els_pipeline.db.SimpleConnectionPool') as mock_pool:
            DatabaseConnection._pool = None
            DatabaseConnection.initialize_pool(
                host='testhost',
                port=5432,
                database='testdb',
                user='testuser',
                password='testpass'
            )
            
            mock_pool.assert_called_once()
            assert DatabaseConnection._pool is not None
    
    def test_initialize_pool_with_env_vars(self):
        """Test connection pool initialization with environment variables."""
        with patch('els_pipeline.db.SimpleConnectionPool') as mock_pool, \
             patch.dict('os.environ', {
                 'DB_HOST': 'envhost',
                 'DB_PORT': '5433',
                 'DB_NAME': 'envdb',
                 'DB_USER': 'envuser',
                 'DB_PASSWORD': 'envpass'
             }):
            DatabaseConnection._pool = None
            DatabaseConnection.initialize_pool()
            
            mock_pool.assert_called_once()
            call_kwargs = mock_pool.call_args[1]
            assert call_kwargs['host'] == 'envhost'
            assert call_kwargs['port'] == 5433
            assert call_kwargs['database'] == 'envdb'


class TestPersistStandard:
    """Tests for persist_standard function."""
    
    def test_persist_standard_with_all_levels(self, mock_connection, sample_standard):
        """Test persisting a standard with all hierarchy levels."""
        conn, cursor = mock_connection
        cursor.fetchone.side_effect = [(1,), (2,), (3,), (4,)]  # document_id, domain_id, strand_id, sub_strand_id
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            document_meta = {
                'title': 'California Preschool Learning Foundations',
                'source_url': 'https://example.com',
                'age_band': '3-5',
                'publishing_agency': 'California Department of Education'
            }
            
            persist_standard(sample_standard, document_meta)
            
            # Verify document insert
            assert cursor.execute.call_count >= 4
            first_call = cursor.execute.call_args_list[0]
            assert 'INSERT INTO documents' in first_call[0][0]
            assert sample_standard.country in first_call[0][1]
            assert sample_standard.state in first_call[0][1]
            
            conn.commit.assert_called_once()
    
    def test_persist_standard_without_strand_sub_strand(self, mock_connection):
        """Test persisting a standard without strand and sub_strand."""
        conn, cursor = mock_connection
        cursor.fetchone.side_effect = [(1,), (2,)]  # document_id, domain_id
        
        standard = NormalizedStandard(
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
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            document_meta = {
                'title': 'Texas Standards',
                'source_url': 'https://example.com',
                'age_band': '0-3',
                'publishing_agency': 'Texas Education Agency'
            }
            
            persist_standard(standard, document_meta)
            
            # Should only insert document, domain, and indicator (no strand/sub_strand)
            conn.commit.assert_called_once()


class TestPersistEmbedding:
    """Tests for persist_embedding function."""
    
    def test_persist_embedding(self, mock_connection, sample_embedding):
        """Test persisting an embedding record."""
        conn, cursor = mock_connection
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            persist_embedding(sample_embedding)
            
            # Verify embedding insert
            cursor.execute.assert_called_once()
            call_args = cursor.execute.call_args[0]
            assert 'INSERT INTO embeddings' in call_args[0]
            assert sample_embedding.indicator_id in call_args[1]
            assert sample_embedding.country in call_args[1]
            assert sample_embedding.state in call_args[1]
            
            conn.commit.assert_called_once()


class TestPersistRecommendation:
    """Tests for persist_recommendation function."""
    
    def test_persist_recommendation(self, mock_connection, sample_recommendation):
        """Test persisting a recommendation."""
        conn, cursor = mock_connection
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            persist_recommendation(sample_recommendation)
            
            # Verify recommendation insert
            cursor.execute.assert_called_once()
            call_args = cursor.execute.call_args[0]
            assert 'INSERT INTO recommendations' in call_args[0]
            assert sample_recommendation.recommendation_id in call_args[1]
            assert sample_recommendation.country in call_args[1]
            assert sample_recommendation.state in call_args[1]
            
            conn.commit.assert_called_once()


class TestQuerySimilarIndicators:
    """Tests for query_similar_indicators function."""
    
    def test_query_without_filters(self, mock_connection):
        """Test querying similar indicators without filters."""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {
                'standard_id': 'US-CA-2021-LLD-1.2',
                'code': 'LLD.A.1.a',
                'description': 'Test description',
                'domain_code': 'LLD',
                'domain_name': 'Language',
                'country': 'US',
                'state': 'CA',
                'age_band': '3-5',
                'version_year': 2021,
                'similarity': 0.95
            }
        ]
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            vector = [0.1] * 1536
            results = query_similar_indicators(vector, top_k=10)
            
            assert len(results) == 1
            assert results[0]['standard_id'] == 'US-CA-2021-LLD-1.2'
            assert results[0]['country'] == 'US'
            cursor.execute.assert_called_once()
    
    def test_query_with_country_state_filters(self, mock_connection):
        """Test querying with country and state filters."""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = []
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            vector = [0.1] * 1536
            filters = {'country': 'US', 'state': 'CA', 'age_band': '3-5'}
            results = query_similar_indicators(vector, top_k=5, filters=filters)
            
            # Verify filters were applied in query
            call_args = cursor.execute.call_args[0]
            assert 'e.country = %s' in call_args[0]
            assert 'e.state = %s' in call_args[0]
            assert 'US' in call_args[1]
            assert 'CA' in call_args[1]


class TestGetIndicatorsByCountryState:
    """Tests for get_indicators_by_country_state function."""
    
    def test_get_indicators_basic(self, mock_connection):
        """Test getting indicators by country and state."""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {
                'standard_id': 'US-CA-2021-LLD-1.2',
                'indicator_code': 'LLD.A.1.a',
                'description': 'Test',
                'domain_code': 'LLD',
                'domain_name': 'Language',
                'country': 'US',
                'state': 'CA',
                'age_band': '3-5',
                'version_year': 2021
            }
        ]
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            results = get_indicators_by_country_state('US', 'CA')
            
            assert len(results) == 1
            assert results[0]['country'] == 'US'
            assert results[0]['state'] == 'CA'
            
            call_args = cursor.execute.call_args[0]
            assert 'd.country = %s' in call_args[0]
            assert 'd.state = %s' in call_args[0]
    
    def test_get_indicators_with_domain_filter(self, mock_connection):
        """Test getting indicators filtered by domain."""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = []
        
        with patch.object(DatabaseConnection, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn
            
            results = get_indicators_by_country_state('US', 'CA', domain_code='LLD')
            
            call_args = cursor.execute.call_args[0]
            assert 'dom.code = %s' in call_args[0]
            assert 'LLD' in call_args[1]
