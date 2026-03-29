"""Data access layer for Aurora PostgreSQL with pgvector."""

import json
import os
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import logging
import boto3

from .models import NormalizedStandard, EmbeddingRecord, Recommendation

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages database connection pooling."""
    
    _pool: Optional[SimpleConnectionPool] = None
    
    @classmethod
    def initialize_pool(
        cls,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
        minconn: int = 1,
        maxconn: int = 10
    ):
        """Initialize the connection pool."""
        if cls._pool is not None:
            logger.warning("Connection pool already initialized")
            return
        
        # Try Secrets Manager first (Lambda environment), then env vars, then defaults
        secret_arn = os.getenv('DB_SECRET_ARN')
        if secret_arn and not all([host, port, database, user, password]):
            secret = cls._get_secret(secret_arn)
            if secret:
                host = host or secret.get('host')
                port = port or int(secret.get('port', '5432'))
                database = database or secret.get('dbname', 'els_pipeline')
                user = user or secret.get('username')
                password = password or secret.get('password')
        
        # Fall back to environment variables
        host = host or os.getenv('DB_HOST', 'localhost')
        port = port or int(os.getenv('DB_PORT', '5432'))
        database = database or os.getenv('DB_NAME', 'els_pipeline')
        user = user or os.getenv('DB_USER', 'postgres')
        password = password or os.getenv('DB_PASSWORD', '')
        
        cls._pool = SimpleConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10,
            options='-c statement_timeout=30000'
        )
        logger.info(f"Database connection pool initialized: {host}:{port}/{database}")

    @classmethod
    def _get_secret(cls, secret_arn: str) -> Optional[Dict[str, str]]:
        """Retrieve database credentials from Secrets Manager."""
        try:
            client = boto3.client('secretsmanager')
            response = client.get_secret_value(SecretId=secret_arn)
            return json.loads(response['SecretString'])
        except Exception as e:
            logger.warning(f"Failed to retrieve secret from Secrets Manager: {e}")
            return None

    
    @classmethod
    @contextmanager
    def get_connection(cls):
        """Get a connection from the pool."""
        if cls._pool is None:
            cls.initialize_pool()
        
        conn = cls._pool.getconn()
        try:
            yield conn
        finally:
            cls._pool.putconn(conn)
    
    @classmethod
    def close_pool(cls):
        """Close all connections in the pool."""
        if cls._pool is not None:
            cls._pool.closeall()
            cls._pool = None
            logger.info("Database connection pool closed")


def persist_standard(standard: NormalizedStandard, document_meta: Dict[str, Any]) -> None:
    """
    Persist a normalized standard to the database.

    Args:
        standard: The normalized standard to persist (includes age_band and
                  hierarchy-level descriptions from the parser)
        document_meta: Document metadata including title, source_url, publishing_agency
    """
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor() as cur:
            try:
                # Insert or get document — age_band comes from the parsed
                # indicator (standard.age_band), not document_meta.
                cur.execute("""
                    INSERT INTO documents (country, state, title, version_year, source_url, s3_key, age_band, publishing_agency)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (country, state, version_year, title) DO UPDATE
                    SET source_url = EXCLUDED.source_url,
                        s3_key = COALESCE(EXCLUDED.s3_key, documents.s3_key),
                        age_band = EXCLUDED.age_band,
                        publishing_agency = EXCLUDED.publishing_agency
                    RETURNING id
                """, (
                    standard.country,
                    standard.state,
                    document_meta['title'],
                    standard.version_year,
                    document_meta.get('source_url'),
                    document_meta.get('s3_key'),
                    standard.age_band or "PK",
                    document_meta['publishing_agency']
                ))
                document_id = cur.fetchone()[0]

                # Insert or get domain (with description)
                cur.execute("""
                    INSERT INTO domains (document_id, code, name, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (document_id, code) DO UPDATE
                    SET name = EXCLUDED.name,
                        description = EXCLUDED.description
                    RETURNING id
                """, (document_id, standard.domain.code, standard.domain.name, standard.domain.description))
                domain_id = cur.fetchone()[0]

                # Insert strand if present (with description)
                strand_id = None
                if standard.strand:
                    cur.execute("""
                        INSERT INTO strands (domain_id, code, name, description)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (domain_id, code) DO UPDATE
                        SET name = EXCLUDED.name,
                            description = EXCLUDED.description
                        RETURNING id
                    """, (domain_id, standard.strand.code, standard.strand.name, standard.strand.description))
                    strand_id = cur.fetchone()[0]

                # Insert sub_strand if present (with description)
                sub_strand_id = None
                if standard.sub_strand and strand_id:
                    cur.execute("""
                        INSERT INTO sub_strands (strand_id, code, name, description)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (strand_id, code) DO UPDATE
                        SET name = EXCLUDED.name,
                            description = EXCLUDED.description
                        RETURNING id
                    """, (strand_id, standard.sub_strand.code, standard.sub_strand.name, standard.sub_strand.description))
                    sub_strand_id = cur.fetchone()[0]

                # Insert indicator (with title, description, and age_band from parsed data)
                cur.execute("""
                    INSERT INTO indicators (
                        standard_id, domain_id, strand_id, sub_strand_id,
                        code, title, description, age_band, source_page, source_text
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (standard_id) DO UPDATE
                    SET domain_id = EXCLUDED.domain_id,
                        strand_id = EXCLUDED.strand_id,
                        sub_strand_id = EXCLUDED.sub_strand_id,
                        code = EXCLUDED.code,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        age_band = EXCLUDED.age_band,
                        source_page = EXCLUDED.source_page,
                        source_text = EXCLUDED.source_text
                """, (
                    standard.standard_id,
                    domain_id,
                    strand_id,
                    sub_strand_id,
                    standard.indicator.code,
                    standard.indicator.name or None,
                    standard.indicator.description or "",
                    standard.age_band,
                    standard.source_page,
                    standard.source_text
                ))

                conn.commit()
                logger.info(f"Persisted standard: {standard.standard_id}")

            except Exception as e:
                conn.rollback()
                logger.error(f"Error persisting standard {standard.standard_id}: {e}")
                raise


def persist_embedding(record: EmbeddingRecord) -> None:
    """
    Persist an embedding record to the database.
    
    Args:
        record: The embedding record to persist
    """
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor() as cur:
            try:
                # Convert vector list to PostgreSQL array format
                vector_str = '[' + ','.join(str(v) for v in record.vector) + ']'
                
                cur.execute("""
                    INSERT INTO embeddings (
                        indicator_id, country, state, vector,
                        embedding_model, embedding_version, input_text, created_at
                    )
                    VALUES (%s, %s, %s, %s::vector, %s, %s, %s, %s)
                """, (
                    record.indicator_id,
                    record.country,
                    record.state,
                    vector_str,
                    record.embedding_model,
                    record.embedding_version,
                    record.input_text,
                    record.created_at
                ))
                
                conn.commit()
                logger.info(f"Persisted embedding for indicator: {record.indicator_id}")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error persisting embedding for {record.indicator_id}: {e}")
                raise


def persist_recommendation(rec: Recommendation) -> None:
    """
    Persist a recommendation to the database.
    
    Args:
        rec: The recommendation to persist
    """
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO recommendations (
                        recommendation_id, indicator_id, country, state,
                        audience, activity_description, age_band,
                        generation_model, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (recommendation_id) DO UPDATE
                    SET activity_description = EXCLUDED.activity_description,
                        generation_model = EXCLUDED.generation_model
                """, (
                    rec.recommendation_id,
                    rec.indicator_id,
                    rec.country,
                    rec.state,
                    rec.audience.value,
                    rec.activity_description,
                    rec.age_band,
                    rec.generation_model,
                    rec.created_at
                ))
                
                conn.commit()
                logger.info(f"Persisted recommendation: {rec.recommendation_id}")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error persisting recommendation {rec.recommendation_id}: {e}")
                raise


def query_similar_indicators(
    vector: List[float],
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Query for similar indicators using vector similarity search.
    
    Args:
        vector: The query vector
        top_k: Number of results to return
        filters: Optional filters (country, state, age_band, domain, version_year)
    
    Returns:
        List of indicator records with similarity scores
    """
    filters = filters or {}
    
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Build the WHERE clause based on filters
            where_clauses = []
            params = []
            
            if 'country' in filters:
                where_clauses.append("e.country = %s")
                params.append(filters['country'])
            
            if 'state' in filters:
                where_clauses.append("e.state = %s")
                params.append(filters['state'])
            
            if 'age_band' in filters:
                where_clauses.append("d.age_band = %s")
                params.append(filters['age_band'])
            
            if 'domain' in filters:
                where_clauses.append("dom.code = %s")
                params.append(filters['domain'])
            
            if 'version_year' in filters:
                where_clauses.append("d.version_year = %s")
                params.append(filters['version_year'])
            
            where_clause = " AND " + " AND ".join(where_clauses) if where_clauses else ""
            
            # Convert vector to PostgreSQL array format
            vector_str = '[' + ','.join(str(v) for v in vector) + ']'
            
            query = f"""
                SELECT 
                    i.standard_id,
                    i.code,
                    i.description,
                    dom.code as domain_code,
                    dom.name as domain_name,
                    d.country,
                    d.state,
                    d.age_band,
                    d.version_year,
                    1 - (e.vector <=> %s::vector) as similarity
                FROM embeddings e
                JOIN indicators i ON e.indicator_id = i.standard_id
                JOIN domains dom ON i.domain_id = dom.id
                JOIN documents d ON dom.document_id = d.id
                {where_clause}
                ORDER BY e.vector <=> %s::vector
                LIMIT %s
            """
            
            params = [vector_str, vector_str] + params + [top_k]
            cur.execute(query, params)
            
            results = cur.fetchall()
            return [dict(row) for row in results]


def get_indicators_by_country_state(
    country: str,
    state: str,
    domain_code: Optional[str] = None,
    strand_code: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all indicators for a specific country and state, optionally filtered by domain/strand.
    
    Args:
        country: Two-letter country code
        state: State code
        domain_code: Optional domain code filter
        strand_code: Optional strand code filter
    
    Returns:
        List of indicator records
    """
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where_clauses = ["d.country = %s", "d.state = %s"]
            params = [country, state]
            
            if domain_code:
                where_clauses.append("dom.code = %s")
                params.append(domain_code)
            
            if strand_code:
                where_clauses.append("str.code = %s")
                params.append(strand_code)
            
            where_clause = " AND ".join(where_clauses)
            
            query = f"""
                SELECT 
                    i.standard_id,
                    i.code as indicator_code,
                    i.title as indicator_title,
                    i.description,
                    dom.code as domain_code,
                    dom.name as domain_name,
                    dom.description as domain_description,
                    str.code as strand_code,
                    str.name as strand_name,
                    str.description as strand_description,
                    substr.code as sub_strand_code,
                    substr.name as sub_strand_name,
                    substr.description as sub_strand_description,
                    i.age_band as indicator_age_band,
                    d.country,
                    d.state,
                    d.age_band,
                    d.version_year,
                    i.source_page
                FROM indicators i
                JOIN domains dom ON i.domain_id = dom.id
                JOIN documents d ON dom.document_id = d.id
                LEFT JOIN strands str ON i.strand_id = str.id
                LEFT JOIN sub_strands substr ON i.sub_strand_id = substr.id
                WHERE {where_clause}
                ORDER BY i.standard_id
            """
            
            cur.execute(query, params)
            results = cur.fetchall()
            return [dict(row) for row in results]
