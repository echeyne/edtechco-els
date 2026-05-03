"""Shared configuration for the ELS pipeline."""

import os


class Config:
    """Shared configuration constants for the ELS pipeline."""
    
    # S3 Bucket Names
    S3_RAW_BUCKET = os.getenv("ELS_RAW_BUCKET", "els-raw-documents")
    S3_PROCESSED_BUCKET = os.getenv("ELS_PROCESSED_BUCKET", "els-processed-json")
    S3_EMBEDDINGS_BUCKET = os.getenv("ELS_EMBEDDINGS_BUCKET", "els-embeddings")
    
    # Bedrock Model IDs
    # Use cross-region inference profile for Anthropic models
    BEDROCK_DETECTOR_LLM_MODEL_ID = os.getenv("BEDROCK_DETECTOR_LLM_MODEL_ID", "us.anthropic.claude-opus-4-7")
    BEDROCK_PARSER_LLM_MODEL_ID = os.getenv("BEDROCK_PARSER_LLM_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
    BEDROCK_EMBEDDING_MODEL_ID = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1")
    # Pass-1 (depth-map inference) is structural-summary work — Haiku is plenty
    # and avoids the Opus token-rate ceiling that throttles back-to-back calls.
    BEDROCK_DEPTH_MAP_LLM_MODEL_ID = os.getenv(
        "BEDROCK_DEPTH_MAP_LLM_MODEL_ID", "us.anthropic.claude-haiku-4-5"
    )
    
    # Confidence Threshold
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    
    # Batch Configuration
    MAX_CHUNKS_PER_BATCH = int(os.getenv("MAX_CHUNKS_PER_BATCH", "5"))
    MAX_DOMAINS_PER_BATCH = int(os.getenv("MAX_DOMAINS_PER_BATCH", "3"))
    
    # AWS Region
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    
    # Database Configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "els_corpus")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    # Step Functions Configuration
    STEP_FUNCTIONS_STATE_MACHINE_ARN = os.getenv(
        "STEP_FUNCTIONS_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:123456789012:stateMachine:els-pipeline"
    )

