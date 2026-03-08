#!/usr/bin/env python3
"""Manual test script for database operations with real Aurora PostgreSQL.

This script tests the database access layer with a real Aurora PostgreSQL cluster.
It verifies:
- Connection pooling
- Standard persistence
- Embedding persistence
- Recommendation persistence
- Vector similarity search
- Indicator retrieval by country and state

Prerequisites:
- Aurora PostgreSQL cluster deployed via CloudFormation
- Database initialized with schema from infra/migrations/001_initial_schema.sql
- Environment variables set (see below)

Environment Variables:
    DB_HOST: Aurora cluster endpoint (e.g., els-database-cluster-dev.cluster-xxxxx.us-east-1.rds.amazonaws.com)
    DB_PORT: Database port (default: 5432)
    DB_NAME: Database name (default: els_pipeline)
    DB_USER: Database username (from Secrets Manager)
    DB_PASSWORD: Database password (from Secrets Manager)

Usage:
    # Set environment variables
    export DB_HOST="your-cluster-endpoint"
    export DB_USER="els_admin"
    export DB_PASSWORD="your-password"
    
    # Run the test script
    python scripts/test_db_manual.py
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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


def check_environment():
    """Check that required environment variables are set."""
    required_vars = ['DB_HOST', 'DB_USER', 'DB_PASSWORD']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set the required environment variables and try again.")
        print("See the script docstring for details.")
        sys.exit(1)
    
    print("✅ Environment variables configured")
    print(f"   DB_HOST: {os.getenv('DB_HOST')}")
    print(f"   DB_PORT: {os.getenv('DB_PORT', '5432')}")
    print(f"   DB_NAME: {os.getenv('DB_NAME', 'els_pipeline')}")
    print(f"   DB_USER: {os.getenv('DB_USER')}")
    print()


def test_connection_pool():
    """Test database connection pool initialization."""
    print("Testing connection pool initialization...")
    
    try:
        DatabaseConnection.initialize_pool(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'els_pipeline'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            minconn=1,
            maxconn=5
        )
        print("✅ Connection pool initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Connection pool initialization failed: {e}")
        return False


def test_persist_standard():
    """Test persisting a standard to the database."""
    print("\nTesting standard persistence...")
    
    try:
        standard = NormalizedStandard(
            standard_id="US-TEST-2024-TST-1",
            country="US",
            state="TEST",
            version_year=2024,
            domain=HierarchyLevel(code="TST", name="Test Domain"),
            strand=HierarchyLevel(code="TST.A", name="Test Strand"),
            sub_strand=None,
            indicator=HierarchyLevel(
                code="TST.A.1",
                name="Test Indicator",
                description="This is a test indicator for manual testing."
            ),
            source_page=1,
            source_text="Test source text"
        )
        
        document_meta = {
            'title': 'Manual Test Standards',
            'source_url': 'https://example.com/test',
            'age_band': '3-5',
            'publishing_agency': 'Test Agency'
        }
        
        persist_standard(standard, document_meta)
        print(f"✅ Standard persisted: {standard.standard_id}")
        return True
    except Exception as e:
        print(f"❌ Standard persistence failed: {e}")
        return False


def test_persist_embedding():
    """Test persisting an embedding to the database."""
    print("\nTesting embedding persistence...")
    
    try:
        # Generate a simple test vector
        test_vector = [0.1] * 1536
        
        embedding = EmbeddingRecord(
            indicator_id="US-TEST-2024-TST-1",
            country="US",
            state="TEST",
            vector=test_vector,
            embedding_model="amazon.titan-embed-text-v1",
            embedding_version="v1",
            input_text="Test Domain – Test Strand – This is a test indicator for manual testing. Age 3-5.",
            created_at=datetime.now().isoformat()
        )
        
        persist_embedding(embedding)
        print(f"✅ Embedding persisted for: {embedding.indicator_id}")
        return True
    except Exception as e:
        print(f"❌ Embedding persistence failed: {e}")
        return False


def test_persist_recommendations():
    """Test persisting recommendations to the database."""
    print("\nTesting recommendation persistence...")
    
    try:
        recommendations = [
            Recommendation(
                recommendation_id="rec-test-parent-001",
                indicator_id="US-TEST-2024-TST-1",
                country="US",
                state="TEST",
                audience=AudienceEnum.PARENT,
                activity_description="Engage in interactive play activities that promote learning.",
                age_band="3-5",
                generation_model="anthropic.claude-v2",
                created_at=datetime.now().isoformat()
            ),
            Recommendation(
                recommendation_id="rec-test-teacher-001",
                indicator_id="US-TEST-2024-TST-1",
                country="US",
                state="TEST",
                audience=AudienceEnum.TEACHER,
                activity_description="Create structured learning opportunities in the classroom.",
                age_band="3-5",
                generation_model="anthropic.claude-v2",
                created_at=datetime.now().isoformat()
            )
        ]
        
        for rec in recommendations:
            persist_recommendation(rec)
            print(f"✅ Recommendation persisted: {rec.recommendation_id} ({rec.audience.value})")
        
        return True
    except Exception as e:
        print(f"❌ Recommendation persistence failed: {e}")
        return False


def test_vector_similarity_search():
    """Test vector similarity search."""
    print("\nTesting vector similarity search...")
    
    try:
        # Use the same test vector we persisted
        query_vector = [0.1] * 1536
        
        results = query_similar_indicators(
            vector=query_vector,
            top_k=5,
            filters={'country': 'US', 'state': 'TEST'}
        )
        
        print(f"✅ Similarity search returned {len(results)} results")
        
        if results:
            print("\n   Top result:")
            top_result = results[0]
            print(f"   - Standard ID: {top_result['standard_id']}")
            print(f"   - Description: {top_result['description']}")
            print(f"   - Similarity: {top_result['similarity']:.4f}")
        
        return True
    except Exception as e:
        print(f"❌ Vector similarity search failed: {e}")
        return False


def test_get_indicators():
    """Test retrieving indicators by country and state."""
    print("\nTesting indicator retrieval...")
    
    try:
        results = get_indicators_by_country_state('US', 'TEST')
        
        print(f"✅ Retrieved {len(results)} indicators for US/TEST")
        
        if results:
            print("\n   Sample indicator:")
            indicator = results[0]
            print(f"   - Standard ID: {indicator['standard_id']}")
            print(f"   - Domain: {indicator['domain_name']} ({indicator['domain_code']})")
            print(f"   - Description: {indicator['description']}")
        
        # Test with domain filter
        results_filtered = get_indicators_by_country_state('US', 'TEST', domain_code='TST')
        print(f"✅ Retrieved {len(results_filtered)} indicators for US/TEST/TST domain")
        
        return True
    except Exception as e:
        print(f"❌ Indicator retrieval failed: {e}")
        return False


def test_pgvector_extension():
    """Test that pgvector extension is installed and working."""
    print("\nTesting pgvector extension...")
    
    try:
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if pgvector extension is installed
                cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
                result = cur.fetchone()
                
                if result:
                    print(f"✅ pgvector extension installed: version {result[1]}")
                    return True
                else:
                    print("❌ pgvector extension not found")
                    return False
    except Exception as e:
        print(f"❌ pgvector extension check failed: {e}")
        return False


def cleanup_test_data():
    """Clean up test data from the database."""
    print("\nCleaning up test data...")
    
    try:
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                # Delete in reverse order of foreign key dependencies
                cur.execute("DELETE FROM recommendations WHERE indicator_id LIKE 'US-TEST-%'")
                cur.execute("DELETE FROM embeddings WHERE indicator_id LIKE 'US-TEST-%'")
                cur.execute("DELETE FROM indicators WHERE standard_id LIKE 'US-TEST-%'")
                cur.execute("DELETE FROM sub_strands WHERE id IN (SELECT ss.id FROM sub_strands ss JOIN strands str ON ss.strand_id = str.id JOIN domains d ON str.domain_id = d.id JOIN documents doc ON d.document_id = doc.id WHERE doc.state = 'TEST')")
                cur.execute("DELETE FROM strands WHERE id IN (SELECT str.id FROM strands str JOIN domains d ON str.domain_id = d.id JOIN documents doc ON d.document_id = doc.id WHERE doc.state = 'TEST')")
                cur.execute("DELETE FROM domains WHERE id IN (SELECT d.id FROM domains d JOIN documents doc ON d.document_id = doc.id WHERE doc.state = 'TEST')")
                cur.execute("DELETE FROM documents WHERE state = 'TEST'")
                
                conn.commit()
                print("✅ Test data cleaned up")
                return True
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False


def main():
    """Run all manual database tests."""
    print("=" * 70)
    print("ELS Pipeline - Manual Database Testing")
    print("=" * 70)
    print()
    
    # Check environment
    check_environment()
    
    # Track test results
    results = {}
    
    # Run tests
    results['connection_pool'] = test_connection_pool()
    
    if results['connection_pool']:
        results['pgvector'] = test_pgvector_extension()
        results['persist_standard'] = test_persist_standard()
        results['persist_embedding'] = test_persist_embedding()
        results['persist_recommendations'] = test_persist_recommendations()
        results['similarity_search'] = test_vector_similarity_search()
        results['get_indicators'] = test_get_indicators()
        results['cleanup'] = cleanup_test_data()
    
    # Close connection pool
    DatabaseConnection.close_pool()
    
    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"{test_name:30s} {status}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == '__main__':
    main()
