"""Property-based tests for query layer.

Feature: els-normalization-pipeline
Properties: 19, 20
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import patch, MagicMock
import random

from els_pipeline.db import query_similar_indicators


# Strategies for generating test data
@st.composite
def vector_strategy(draw):
    """Generate a random embedding vector with reduced dimension for testing."""
    # Use smaller dimension for faster testing
    dimension = 128  # Reduced from 1536
    return [draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)) for _ in range(dimension)]


@st.composite
def indicator_record_strategy(draw, country=None, state=None, age_band=None, domain=None):
    """Generate a random indicator record with optional fixed values."""
    return {
        'standard_id': draw(st.text(min_size=10, max_size=50)),
        'code': draw(st.text(min_size=3, max_size=20)),
        'description': draw(st.text(min_size=10, max_size=200)),
        'domain_code': domain if domain else draw(st.text(min_size=2, max_size=10)),
        'domain_name': draw(st.text(min_size=5, max_size=50)),
        'country': country if country else draw(st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))),
        'state': state if state else draw(st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',)))),
        'age_band': age_band if age_band else draw(st.sampled_from(['0-3', '3-5', '5-8'])),
        'version_year': draw(st.integers(min_value=2000, max_value=2030)),
        'similarity': draw(st.floats(min_value=0.0, max_value=1.0))
    }


@st.composite
def similarity_ordered_records_strategy(draw):
    """Generate a list of records with decreasing similarity scores."""
    count = draw(st.integers(min_value=2, max_value=10))
    records = []
    
    # Generate similarity scores in decreasing order
    similarities = sorted([draw(st.floats(min_value=0.0, max_value=1.0)) for _ in range(count)], reverse=True)
    
    for similarity in similarities:
        record = draw(indicator_record_strategy())
        record['similarity'] = similarity
        records.append(record)
    
    return records


class TestProperty19VectorSimilarityOrdering:
    """Property 19: Vector Similarity Ordering
    
    For any query vector and set of stored embedding vectors, the results returned by
    query_similar_indicators SHALL be ordered by decreasing cosine similarity.
    
    Validates: Requirements 7.3
    """
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        mock_results=similarity_ordered_records_strategy()
    )
    def test_results_ordered_by_decreasing_similarity(self, query_vector, mock_results):
        """Test that query results are ordered by decreasing similarity."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Shuffle the results to simulate unordered database return
            shuffled_results = mock_results.copy()
            random.shuffle(shuffled_results)
            
            # Mock should return ordered results (simulating ORDER BY in SQL)
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query
            results = query_similar_indicators(query_vector, top_k=len(mock_results))
            
            # Property: Results must be ordered by decreasing similarity
            similarities = [r['similarity'] for r in results]
            assert similarities == sorted(similarities, reverse=True), \
                f"Results not ordered by decreasing similarity: {similarities}"
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        count=st.integers(min_value=1, max_value=20)
    )
    def test_similarity_ordering_with_random_scores(self, query_vector, count):
        """Test ordering property with completely random similarity scores."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate random records with random similarities
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'TEST-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': 'TEST',
                    'domain_name': 'Test Domain',
                    'country': 'US',
                    'state': 'CA',
                    'age_band': '3-5',
                    'version_year': 2021,
                    'similarity': random.random()
                }
                mock_results.append(record)
            
            # Sort by similarity (descending) as the database would
            mock_results.sort(key=lambda x: x['similarity'], reverse=True)
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query
            results = query_similar_indicators(query_vector, top_k=count)
            
            # Property: Each result must have similarity >= next result
            for i in range(len(results) - 1):
                assert results[i]['similarity'] >= results[i + 1]['similarity'], \
                    f"Similarity ordering violated at index {i}: {results[i]['similarity']} < {results[i + 1]['similarity']}"


class TestProperty20QueryFilterCorrectness:
    """Property 20: Query Filter Correctness
    
    For any similarity query with a country filter, all returned indicators SHALL have a
    country value matching the filter. The same holds for state, age_band, domain, and
    version_year filters.
    
    Validates: Requirements 7.4
    """
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        filter_country=st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        count=st.integers(min_value=1, max_value=10)
    )
    def test_country_filter_correctness(self, query_vector, filter_country, count):
        """Test that country filter is correctly applied."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate records with the filtered country
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'{filter_country}-TEST-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': 'TEST',
                    'domain_name': 'Test Domain',
                    'country': filter_country,  # All records match filter
                    'state': 'CA',
                    'age_band': '3-5',
                    'version_year': 2021,
                    'similarity': 0.9 - (i * 0.05)
                }
                mock_results.append(record)
            
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query with country filter
            filters = {'country': filter_country}
            results = query_similar_indicators(query_vector, top_k=count, filters=filters)
            
            # Property: All results must have the filtered country
            for result in results:
                assert result['country'] == filter_country, \
                    f"Result country {result['country']} does not match filter {filter_country}"
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        filter_state=st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
        count=st.integers(min_value=1, max_value=10)
    )
    def test_state_filter_correctness(self, query_vector, filter_state, count):
        """Test that state filter is correctly applied."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate records with the filtered state
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'US-{filter_state}-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': 'TEST',
                    'domain_name': 'Test Domain',
                    'country': 'US',
                    'state': filter_state,  # All records match filter
                    'age_band': '3-5',
                    'version_year': 2021,
                    'similarity': 0.9 - (i * 0.05)
                }
                mock_results.append(record)
            
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query with state filter
            filters = {'state': filter_state}
            results = query_similar_indicators(query_vector, top_k=count, filters=filters)
            
            # Property: All results must have the filtered state
            for result in results:
                assert result['state'] == filter_state, \
                    f"Result state {result['state']} does not match filter {filter_state}"
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        filter_age_band=st.sampled_from(['0-3', '3-5', '5-8']),
        count=st.integers(min_value=1, max_value=10)
    )
    def test_age_band_filter_correctness(self, query_vector, filter_age_band, count):
        """Test that age_band filter is correctly applied."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate records with the filtered age_band
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'US-CA-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': 'TEST',
                    'domain_name': 'Test Domain',
                    'country': 'US',
                    'state': 'CA',
                    'age_band': filter_age_band,  # All records match filter
                    'version_year': 2021,
                    'similarity': 0.9 - (i * 0.05)
                }
                mock_results.append(record)
            
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query with age_band filter
            filters = {'age_band': filter_age_band}
            results = query_similar_indicators(query_vector, top_k=count, filters=filters)
            
            # Property: All results must have the filtered age_band
            for result in results:
                assert result['age_band'] == filter_age_band, \
                    f"Result age_band {result['age_band']} does not match filter {filter_age_band}"
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        filter_domain=st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
        count=st.integers(min_value=1, max_value=10)
    )
    def test_domain_filter_correctness(self, query_vector, filter_domain, count):
        """Test that domain filter is correctly applied."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate records with the filtered domain
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'US-CA-{filter_domain}-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': filter_domain,  # All records match filter
                    'domain_name': f'{filter_domain} Domain',
                    'country': 'US',
                    'state': 'CA',
                    'age_band': '3-5',
                    'version_year': 2021,
                    'similarity': 0.9 - (i * 0.05)
                }
                mock_results.append(record)
            
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query with domain filter
            filters = {'domain': filter_domain}
            results = query_similar_indicators(query_vector, top_k=count, filters=filters)
            
            # Property: All results must have the filtered domain
            for result in results:
                assert result['domain_code'] == filter_domain, \
                    f"Result domain_code {result['domain_code']} does not match filter {filter_domain}"
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        filter_year=st.integers(min_value=2000, max_value=2030),
        count=st.integers(min_value=1, max_value=10)
    )
    def test_version_year_filter_correctness(self, query_vector, filter_year, count):
        """Test that version_year filter is correctly applied."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate records with the filtered version_year
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'US-CA-{filter_year}-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': 'TEST',
                    'domain_name': 'Test Domain',
                    'country': 'US',
                    'state': 'CA',
                    'age_band': '3-5',
                    'version_year': filter_year,  # All records match filter
                    'similarity': 0.9 - (i * 0.05)
                }
                mock_results.append(record)
            
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query with version_year filter
            filters = {'version_year': filter_year}
            results = query_similar_indicators(query_vector, top_k=count, filters=filters)
            
            # Property: All results must have the filtered version_year
            for result in results:
                assert result['version_year'] == filter_year, \
                    f"Result version_year {result['version_year']} does not match filter {filter_year}"
    
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    @given(
        query_vector=vector_strategy(),
        filter_country=st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        filter_state=st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
        filter_age_band=st.sampled_from(['0-3', '3-5', '5-8']),
        count=st.integers(min_value=1, max_value=10)
    )
    def test_multiple_filters_correctness(self, query_vector, filter_country, filter_state, filter_age_band, count):
        """Test that multiple filters are correctly applied together."""
        with patch('els_pipeline.db.DatabaseConnection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Generate records matching all filters
            mock_results = []
            for i in range(count):
                record = {
                    'standard_id': f'{filter_country}-{filter_state}-{i}',
                    'code': f'CODE-{i}',
                    'description': f'Description {i}',
                    'domain_code': 'TEST',
                    'domain_name': 'Test Domain',
                    'country': filter_country,
                    'state': filter_state,
                    'age_band': filter_age_band,
                    'version_year': 2021,
                    'similarity': 0.9 - (i * 0.05)
                }
                mock_results.append(record)
            
            mock_cursor.fetchall.return_value = mock_results
            
            # Execute query with multiple filters
            filters = {
                'country': filter_country,
                'state': filter_state,
                'age_band': filter_age_band
            }
            results = query_similar_indicators(query_vector, top_k=count, filters=filters)
            
            # Property: All results must match all filters
            for result in results:
                assert result['country'] == filter_country, \
                    f"Result country {result['country']} does not match filter {filter_country}"
                assert result['state'] == filter_state, \
                    f"Result state {result['state']} does not match filter {filter_state}"
                assert result['age_band'] == filter_age_band, \
                    f"Result age_band {result['age_band']} does not match filter {filter_age_band}"
