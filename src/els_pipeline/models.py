"""Core data models for the ELS pipeline."""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import re


def _blank_to_none(v: Any) -> Any:
    """Fold an empty or whitespace-only string to ``None``.

    Applied as a ``mode="before"`` field validator, it covers every construction
    path — ``parser.parse_llm_response``, ``validator.deserialize_record``,
    the batch merge handlers, and any future caller — rather than one call site.
    """
    if isinstance(v, str) and not v.strip():
        return None
    return v


class HierarchyLevelEnum(str, Enum):
    """Valid hierarchy levels."""
    DOMAIN = "domain"
    STRAND = "strand"
    SUB_STRAND = "sub_strand"
    INDICATOR = "indicator"


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
    # None when the element owns no prose of its own — the common case for a
    # heading (a domain/strand/sub_strand with no introduction, a leaf whose
    # example run is claimed by a lead-in). Optional rather than `str` so that
    # absence is spelled `None` here exactly as it is in the golden sets and in
    # the parser's HierarchyLevel — see _blank_to_none.
    description: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_page: int = Field(gt=0)
    source_text: str
    # Populated for indicators that come from age-banded columns (e.g.
    # "Early (3 to 4 ½ Years)", "PK3", "By 36 months"). None for
    # non-age-banded elements.
    age_band: Optional[str] = None

    @field_validator('description', 'age_band', mode='before')
    @classmethod
    def normalize_blank_to_none(cls, v):
        """An absent description/age_band is None, never "" — see _blank_to_none."""
        return _blank_to_none(v)


class DetectionResult(BaseModel):
    """Result of structure detection."""
    document_s3_key: str
    elements: List[DetectedElement]
    status: str
    error: Optional[str] = None


# Hierarchy Parsing Models

class HierarchyLevel(BaseModel):
    """Represents a single level in the hierarchy."""
    code: str
    name: str
    description: Optional[str] = None

    @field_validator('description', mode='before')
    @classmethod
    def normalize_blank_to_none(cls, v):
        """An absent description is None, never "" — see _blank_to_none."""
        return _blank_to_none(v)


class HierarchyNode(BaseModel):
    """Represents a node in the hierarchy tree."""
    level: HierarchyLevelEnum
    code: str
    name: str
    description: Optional[str] = None
    children: List["HierarchyNode"] = Field(default_factory=list)

    @field_validator('description', mode='before')
    @classmethod
    def normalize_blank_to_none(cls, v):
        """An absent description is None, never "" — see _blank_to_none."""
        return _blank_to_none(v)


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

    @field_validator('age_band', mode='before')
    @classmethod
    def normalize_blank_to_none(cls, v):
        """An absent age_band is None, never "" — see _blank_to_none."""
        return _blank_to_none(v)

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
    status: str

    @field_validator('total_validated')
    @classmethod
    def validate_total_validated(cls, v, info):
        """Validate that total_validated <= total_indicators."""
        total_indicators = info.data.get('total_indicators', 0)
        if v > total_indicators:
            raise ValueError(f"total_validated ({v}) cannot exceed total_indicators ({total_indicators})")
        return v


# Detection Batching Models

class DetectionBatchInfo(BaseModel):
    """Metadata for a single detection batch."""
    batch_index: int = Field(ge=0)
    batch_s3_key: str
    chunk_count: int
    block_count: int


class DetectionBatchManifest(BaseModel):
    """Describes how text-block chunks are split into detection batches."""
    run_id: str
    total_blocks: int
    total_chunks: int
    batch_count: int
    batches: List[DetectionBatchInfo]
    created_at: str


class DetectionBatchResult(BaseModel):
    """Partial detection result from a single batch."""
    batch_index: int = Field(ge=0)
    elements: List[Dict[str, Any]]
    errors: List[str]
    status: StatusEnum


# Parse Batching Models

class ParseBatchInfo(BaseModel):
    """Metadata for a single parse batch."""
    batch_index: int = Field(ge=0)
    batch_s3_key: str
    domain_count: int
    element_count: int


class ParseBatchManifest(BaseModel):
    """Describes how domain chunks are split into parse batches."""
    run_id: str
    total_elements: int
    total_domains: int
    batch_count: int
    batches: List[ParseBatchInfo]
    created_at: str


class ParseBatchResult(BaseModel):
    """Partial parsing result from a single batch."""
    batch_index: int = Field(ge=0)
    standards: List[Dict[str, Any]]
    errors: List[str]
    status: StatusEnum


# Enable forward references for recursive models
HierarchyNode.model_rebuild()
