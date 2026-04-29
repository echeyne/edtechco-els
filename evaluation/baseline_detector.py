"""Rule-based baseline detector for comparison against LLM-based detection.

Uses regex pattern matching and heuristics to detect hierarchy elements
from extracted text blocks. Serves as a baseline for evaluating the
LLM approach's advantage.

Same input/output interface as detect_structure() in detector.py.
"""

import re
import logging
from typing import List, Optional, Tuple

from .models import TextBlock, DetectedElement, DetectionResult, HierarchyLevelEnum
from .config import Config

logger = logging.getLogger(__name__)

# Patterns ordered from most specific (deepest) to least specific (shallowest).
# Each pattern: (compiled_regex, hierarchy_level, confidence)
# The regex matches against the start of a text block's content.

HIERARCHY_PATTERNS: List[Tuple[re.Pattern, HierarchyLevelEnum, float]] = [
    # Indicator patterns: numbered items at depth 3-4
    # e.g., "PK3.I.A.1", "1.2.3", "A.1.a", "I.A.1"
    (
        re.compile(
            r"^(?:PK\d+\.)?"           # optional age prefix
            r"[A-Z0-9]{1,5}\."         # domain-level code
            r"[A-Za-z0-9]{1,5}\."      # strand-level code
            r"[A-Za-z0-9]{1,5}"        # indicator code
            r"[\s\.\)]",               # followed by space, dot, or paren
            re.MULTILINE,
        ),
        HierarchyLevelEnum.INDICATOR,
        0.75,
    ),
    # Sub-strand patterns: lettered/numbered items at depth 2
    # e.g., "A.1", "I.A", "1.2"
    (
        re.compile(
            r"^(?:PK\d+\.)?"
            r"[A-Z0-9]{1,5}\."
            r"[A-Za-z]{1,5}"
            r"[\s\.\)]",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.SUB_STRAND,
        0.65,
    ),
    # Strand patterns: single letter/number with title
    # e.g., "A. Self-Concept", "1. Reading"
    (
        re.compile(
            r"^([A-Z])\.\s+[A-Z][a-z]",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.STRAND,
        0.70,
    ),
    # Domain patterns: keyword-based detection
    (
        re.compile(
            r"^(?:Domain|Area|DOMAIN|AREA)\s*(?:\d+|[IVX]+)?\s*[:\-—]?\s*\w",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.DOMAIN,
        0.80,
    ),
    # Domain patterns: Roman numeral sections
    (
        re.compile(
            r"^([IVX]{1,4})\.\s+[A-Z][a-z]",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.DOMAIN,
        0.70,
    ),
    # Keyword-based strand detection
    (
        re.compile(
            r"^(?:Strand|STRAND|Standard|STANDARD)\s*(?:\d+|[A-Z])?\s*[:\-—]?\s*\w",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.STRAND,
        0.75,
    ),
    # Keyword-based sub-strand detection
    (
        re.compile(
            r"^(?:Sub-?Strand|SUB-?STRAND|Topic|TOPIC|Concept|CONCEPT)\s*(?:\d+|[A-Z])?\s*[:\-—]?\s*\w",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.SUB_STRAND,
        0.70,
    ),
    # Keyword-based indicator detection
    (
        re.compile(
            r"^(?:Indicator|INDICATOR|Foundation|FOUNDATION|Benchmark|BENCHMARK|Objective|OBJECTIVE)\s*(?:\d+|[A-Z])?\s*[:\-—]?\s*\w",
            re.MULTILINE,
        ),
        HierarchyLevelEnum.INDICATOR,
        0.70,
    ),
]

# Pattern to extract a code from the beginning of text
CODE_PATTERN = re.compile(
    r"^(?:PK\d+\.)?"
    r"([A-Z0-9]{1,5}(?:\.[A-Za-z0-9]{1,5})*)"
    r"[\s\.\)\-:]"
)

# Pattern to extract title after code
TITLE_PATTERN = re.compile(
    r"^(?:(?:PK\d+\.)?[A-Z0-9]{1,5}(?:\.[A-Za-z0-9]{1,5})*[\s\.\)\-:]+)?"
    r"(?:Domain|Strand|Sub-?Strand|Standard|Indicator|Foundation|Benchmark|"
    r"Objective|Topic|Concept|Area|DOMAIN|STRAND|STANDARD|INDICATOR)?"
    r"\s*(?:\d+|[IVX]+|[A-Z])?\s*[:\-—]?\s*"
    r"(.+?)(?:\n|$)",
    re.MULTILINE,
)


def _extract_code(text: str) -> str:
    """Extract a hierarchical code from the start of text."""
    match = CODE_PATTERN.match(text.strip())
    if match:
        return match.group(1)
    return ""


def _extract_title(text: str) -> str:
    """Extract the title portion from a text block."""
    # Take the first line as the title candidate
    first_line = text.strip().split("\n")[0].strip()

    # Remove code prefix if present
    code_match = CODE_PATTERN.match(first_line)
    if code_match:
        title = first_line[code_match.end():].strip()
    else:
        # Remove keyword prefixes
        title = re.sub(
            r"^(?:Domain|Strand|Sub-?Strand|Standard|Indicator|Foundation|"
            r"Benchmark|Objective|Topic|Concept|Area)\s*(?:\d+|[IVX]+|[A-Z])?\s*[:\-—]?\s*",
            "",
            first_line,
            flags=re.IGNORECASE,
        )

    # Clean up
    title = title.strip(" :-—.")
    return title[:200] if title else first_line[:200]


def _extract_description(text: str) -> str:
    """Extract description (everything after the first line)."""
    lines = text.strip().split("\n")
    if len(lines) > 1:
        return " ".join(line.strip() for line in lines[1:] if line.strip())
    return ""


def _classify_block(block: TextBlock) -> Optional[DetectedElement]:
    """
    Attempt to classify a single text block using regex patterns.

    Returns None if no pattern matches.
    """
    text = block.text.strip()
    if not text or len(text) < 3:
        return None

    for pattern, level, base_confidence in HIERARCHY_PATTERNS:
        if pattern.search(text):
            code = _extract_code(text)
            title = _extract_title(text)
            description = _extract_description(text)

            if not title:
                continue

            # Adjust confidence based on text characteristics
            confidence = base_confidence
            # Boost if text is short (likely a heading)
            if len(text) < 100:
                confidence = min(1.0, confidence + 0.05)
            # Boost if code was found
            if code:
                confidence = min(1.0, confidence + 0.05)

            needs_review = confidence < Config.CONFIDENCE_THRESHOLD

            return DetectedElement(
                level=level,
                code=code or title[:5].upper().replace(" ", ""),
                title=title,
                description=description,
                confidence=confidence,
                source_page=block.page_number,
                source_text=text[:500],
                needs_review=needs_review,
            )

    return None


def detect_structure_baseline(
    blocks: List[TextBlock],
    document_s3_key: str = "",
) -> DetectionResult:
    """
    Detect hierarchical structure using rule-based regex matching.

    Same interface as detect_structure() in detector.py for direct comparison.

    Args:
        blocks: List of text blocks from text extraction
        document_s3_key: S3 key of the source document

    Returns:
        DetectionResult with detected elements, review count, and status
    """
    logger.info(f"Starting baseline detection for: {document_s3_key}")
    logger.info(f"Input: {len(blocks)} text blocks")

    if not blocks:
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            review_count=0,
            status="error",
            error="No text blocks provided",
        )

    elements: List[DetectedElement] = []

    for block in blocks:
        element = _classify_block(block)
        if element:
            elements.append(element)

    review_count = sum(1 for e in elements if e.needs_review)

    level_counts = {}
    for elem in elements:
        level_counts[elem.level.value] = level_counts.get(elem.level.value, 0) + 1

    logger.info(f"Baseline detection complete: {len(elements)} elements")
    logger.info(f"Elements by level: {level_counts}")
    logger.info(f"Review needed: {review_count}")

    return DetectionResult(
        document_s3_key=document_s3_key,
        elements=elements,
        review_count=review_count,
        status="success",
        error=None,
    )
