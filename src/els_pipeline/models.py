"""Core data models for the ELS pipeline."""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import re


class HierarchyLevelEnum(str, Enum):
    """Valid hierarchy levels."""
    DOMAIN = "domain"
    STRAND = "strand"
    SUB_STRAND = "sub_strand"
    INDICATOR = "indicator"


class AudienceEnum(str, Enum):
    """Valid recommendation audiences."""
    PARENT = "parent"
    TEACHER = "teacher"


class StatusEnum(str, Enum):
    """Valid status values."""
    SUCCESS = "success"
    ERROR = "error"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    RUNNING = "running"


# Text Extraction Models

class TextBlock(BaseModel):
    """Represents a text block extracted from a document."""
    text: str
    page_number: int = Field(gt=0)
    block_type: str
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    confidence: float = Field(ge=0.0, le=1.0)
    geometry: Dict[str, Any]
    
    @field_validator('row_index', 'col_index')
    @classmethod
    def validate_table_indices(cls, v, info):
        """Validate that table cell indices are non-negative if present."""
        if v is not None and v < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        return v


class ExtractionResult(BaseModel):
    """Result of text extraction."""
    document_s3_key: str
    blocks: List[TextBlock]
    total_pages: int = Field(gt=0)
    status: str
    error: Optional[str] = None


# Structure Detection Models

class DetectedElement(BaseModel):
    """Represents a detected hierarchical element."""
    level: HierarchyLevelEnum
    code: str
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_page: int = Field(gt=0)
    source_text: str
    needs_review: bool
    
    @field_validator('needs_review')
    @classmethod
    def validate_needs_review(cls, v, info):
        """Validate needs_review flag based on confidence."""
        confidence = info.data.get('confidence')
        if confidence is not None:
            expected = confidence < 0.7
            if v != expected:
                # Auto-correct based on confidence
                return expected
        return v


class DetectionResult(BaseModel):
    """Result of structure detection."""
    document_s3_key: str
    elements: List[DetectedElement]
    review_count: int = Field(ge=0)
    status: str
    error: Optional[str] = None


# Hierarchy Parsing Models

class HierarchyLevel(BaseModel):
    """Represents a single level in the hierarchy."""
    code: str
    name: str
    description: Optional[str] = None


class HierarchyNode(BaseModel):
    """Represents a node in the hierarchy tree."""
    level: HierarchyLevelEnum
    code: str
    name: str
    description: Optional[str] = None
    children: List["HierarchyNode"] = Field(default_factory=list)


class NormalizedStandard(BaseModel):
    """Represents a fully normalized standard."""
    standard_id: str
    country: str
    state: str
    version_year: int
    domain: HierarchyLevel
    strand: Optional[HierarchyLevel] = None
    sub_strand: Optional[HierarchyLevel] = None
    indicator: HierarchyLevel
    age_band: Optional[str] = None
    source_page: int = Field(gt=0)
    source_text: str
    
    @field_validator('country')
    @classmethod
    def validate_country_code(cls, v):
        """Validate that country is a two-letter ISO 3166-1 alpha-2 code."""
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError(f"country must be a two-letter uppercase ISO 3166-1 alpha-2 code, got: {v}")
        return v


class ParseResult(BaseModel):
    """Result of hierarchy parsing."""
    standards: List[NormalizedStandard]
    indicators: List[Dict[str, Any]]  # Serialized NormalizedStandard objects for S3 persistence
    orphaned_elements: List[DetectedElement]
    status: str
    error: Optional[str] = None


# Validation Models

class ValidationError(BaseModel):
    """Represents a validation error."""
    field_path: str
    message: str
    error_type: str


class ValidationResult(BaseModel):
    """Result of validation."""
    is_valid: bool
    errors: List[ValidationError]
    record: Optional[Dict[str, Any]] = None


# Ingestion Models

class IngestionRequest(BaseModel):
    """Request for document ingestion."""
    file_path: str
    country: str
    state: str
    version_year: int
    source_url: str
    publishing_agency: str
    filename: str
    
    @field_validator('country')
    @classmethod
    def validate_country_code(cls, v):
        """Validate that country is a two-letter ISO 3166-1 alpha-2 code."""
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError(f"country must be a two-letter uppercase ISO 3166-1 alpha-2 code, got: {v}")
        return v


class IngestionResult(BaseModel):
    """Result of document ingestion."""
    s3_key: str
    s3_version_id: str
    metadata: Dict[str, Any]
    status: str
    error: Optional[str] = None


# Embedding Models

class EmbeddingRecord(BaseModel):
    """Represents an embedding record."""
    indicator_id: str
    country: str
    state: str
    vector: List[float] = Field(min_length=1)
    embedding_model: str
    embedding_version: str
    input_text: str
    created_at: str
    
    @field_validator('country')
    @classmethod
    def validate_country_code(cls, v):
        """Validate that country is a two-letter ISO 3166-1 alpha-2 code."""
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError(f"country must be a two-letter uppercase ISO 3166-1 alpha-2 code, got: {v}")
        return v


class EmbeddingResult(BaseModel):
    """Result of embedding generation."""
    records: List[EmbeddingRecord]
    status: str
    error: Optional[str] = None


# Recommendation Models

class Recommendation(BaseModel):
    """Represents a recommendation."""
    recommendation_id: str
    indicator_id: str
    country: str
    state: str
    audience: AudienceEnum
    activity_description: str = Field(min_length=1)
    age_band: str
    generation_model: str
    created_at: str
    
    @field_validator('country')
    @classmethod
    def validate_country_code(cls, v):
        """Validate that country is a two-letter ISO 3166-1 alpha-2 code."""
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError(f"country must be a two-letter uppercase ISO 3166-1 alpha-2 code, got: {v}")
        return v


class RecommendationRequest(BaseModel):
    """Request for recommendation generation."""
    country: str
    state: str
    indicator_ids: Optional[List[str]] = None
    domain_code: Optional[str] = None
    strand_code: Optional[str] = None
    age_band: str
    
    @field_validator('country')
    @classmethod
    def validate_country_code(cls, v):
        """Validate that country is a two-letter ISO 3166-1 alpha-2 code."""
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError(f"country must be a two-letter uppercase ISO 3166-1 alpha-2 code, got: {v}")
        return v


class RecommendationResult(BaseModel):
    """Result of recommendation generation."""
    recommendations: List[Recommendation]
    status: str
    error: Optional[str] = None


# Pipeline Orchestration Models

class PipelineStageResult(BaseModel):
    """Result of a single pipeline stage."""
    stage_name: str
    status: str
    duration_ms: int = Field(ge=0)
    output_artifact: str
    error: Optional[str] = None


class PipelineRunResult(BaseModel):
    """Result of a complete pipeline run."""
    run_id: str
    document_s3_key: str
    country: str = Field(min_length=2, max_length=2, pattern="^[A-Z]{2}$")
    state: str
    version_year: int
    stages: List[PipelineStageResult]
    total_indicators: int = Field(ge=0)
    total_validated: int = Field(ge=0)
    total_embedded: int = Field(ge=0)
    total_recommendations: int = Field(ge=0)
    status: str
    
    @field_validator('total_validated')
    @classmethod
    def validate_total_validated(cls, v, info):
        """Validate that total_validated <= total_indicators."""
        total_indicators = info.data.get('total_indicators', 0)
        if v > total_indicators:
            raise ValueError(f"total_validated ({v}) cannot exceed total_indicators ({total_indicators})")
        return v
    
    @field_validator('total_embedded')
    @classmethod
    def validate_total_embedded(cls, v, info):
        """Validate that total_embedded <= total_validated."""
        total_validated = info.data.get('total_validated', 0)
        if v > total_validated:
            raise ValueError(f"total_embedded ({v}) cannot exceed total_validated ({total_validated})")
        return v


# Enable forward references for recursive models
HierarchyNode.model_rebuild()
