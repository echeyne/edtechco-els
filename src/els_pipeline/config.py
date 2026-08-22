"""Shared configuration for the ELS pipeline."""

import os


class Config:
    """Shared configuration constants for the ELS pipeline."""
    
    # S3 Bucket Names
    S3_RAW_BUCKET = os.getenv("ELS_RAW_BUCKET", "els-raw-documents")
    S3_PROCESSED_BUCKET = os.getenv("ELS_PROCESSED_BUCKET", "els-processed-json")

    # Bedrock Model IDs
    # Use cross-region inference profile for Anthropic models
    BEDROCK_DETECTOR_LLM_MODEL_ID = os.getenv("BEDROCK_DETECTOR_LLM_MODEL_ID", "us.anthropic.claude-opus-4-6-v1")
    # Pass-1 (depth-map inference) is structural-summary work — Haiku is plenty
    # and avoids the Opus token-rate ceiling that throttles back-to-back calls.
    BEDROCK_DEPTH_MAP_LLM_MODEL_ID = os.getenv(
        "BEDROCK_DEPTH_MAP_LLM_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    BEDROCK_PARSER_LLM_MODEL_ID = os.getenv("BEDROCK_PARSER_LLM_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

    # Pass-1 depth-map inference on/off. PRODUCTION DEFAULT IS ON and must stay
    # that way — this exists solely for the arXiv paper's depth-map ablation
    # (Task 3), which is the evidence for the "classify by nesting POSITION,
    # not document label" claim. Set ELS_DEPTH_MAP_ENABLED=false to run the
    # off-arm. Read through `Config.DEPTH_MAP_ENABLED` at CALL time (not
    # captured at import) so a test can monkeypatch the attribute.
    DEPTH_MAP_ENABLED = os.getenv("ELS_DEPTH_MAP_ENABLED", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )

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

