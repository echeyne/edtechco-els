"""Structure detection module for ELS pipeline."""

import json
import logging
import re
from typing import List, Dict, Any, Optional
import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError

from .models import TextBlock, DetectedElement, DetectionResult, HierarchyLevelEnum
from .config import Config
from .metrics import (
    LLMCallMetrics,
    MetricsTimer,
    extract_usage_from_response,
    emit_cloudwatch_metrics,
    log_llm_call_metrics,
)

logger = logging.getLogger(__name__)

# Constants
CHARS_PER_TOKEN = 4
DEFAULT_TARGET_TOKENS = 2000

# Trailing footnote/reference markers ("…rules.*", "…health †") are typography,
# not part of the title — the LLM transcribes them inconsistently across runs,
# so a title matches the golden on one run and misses on the next. Strip a
# trailing run of whitespace + footnote glyphs while preserving terminal
# sentence punctuation ("…rules.*" → "…rules.").
_TRAILING_MARKER_RE = re.compile(r"[\s*†‡§¶]+$")

DEFAULT_OVERLAP_TOKENS = 500
MAX_PARSE_RETRIES = 2
MAX_BEDROCK_RETRIES = 2
LLM_MAX_TOKENS = 16000

# Extraction must be as repeatable as the model allows — two runs over the same
# text should yield the same JSON. We pin temperature to 0, but only for models
# that still accept sampling params. Opus 4.7/4.8 and Fable removed
# temperature/top_p/top_k (a 400 if sent); Opus 4.6 and Haiku 4.5 still accept
# them. Match on the substrings in the model id (which carry a region prefix,
# e.g. "us.anthropic.claude-opus-4-6-v1").
LLM_TEMPERATURE = 0.0
_TEMPERATURE_UNSUPPORTED = ("opus-4-7", "opus-4-8", "fable")


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string.
    Uses a simple heuristic: ~4 characters per token.
    
    Args:
        text: Input text string
        
    Returns:
        Estimated token count
    """
    return len(text) // CHARS_PER_TOKEN


def _create_overlap_blocks(chunk: List[TextBlock], overlap_tokens: int) -> tuple[List[TextBlock], int]:
    """
    Create overlap blocks from the end of a chunk.
    
    Args:
        chunk: Current chunk of text blocks
        overlap_tokens: Target number of tokens for overlap
        
    Returns:
        Tuple of (overlap blocks, total overlap tokens)
    """
    overlap_blocks = []
    overlap_token_count = 0
    
    for prev_block in reversed(chunk):
        prev_tokens = estimate_tokens(prev_block.text)
        if overlap_token_count + prev_tokens <= overlap_tokens:
            overlap_blocks.insert(0, prev_block)
            overlap_token_count += prev_tokens
        else:
            break
    
    return overlap_blocks, overlap_token_count


def chunk_text_blocks(
    blocks: List[TextBlock], 
    target_tokens: int = DEFAULT_TARGET_TOKENS, 
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> List[List[TextBlock]]:
    """
    Chunk text blocks into groups of approximately target_tokens with overlap.
    
    This ensures the LLM can process large documents while maintaining context
    across chunk boundaries through overlapping content.
    
    Args:
        blocks: List of text blocks to chunk
        target_tokens: Target number of tokens per chunk (default: 2000)
        overlap_tokens: Number of tokens to overlap between chunks (default: 200)
        
    Returns:
        List of text block chunks, each containing approximately target_tokens
    """
    if not blocks:
        return []
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for block in blocks:
        block_tokens = estimate_tokens(block.text)
        
        # If adding this block would exceed target, finalize current chunk
        if current_chunk and current_tokens + block_tokens > target_tokens:
            chunks.append(current_chunk)
            
            # Create overlap from the end of the previous chunk
            overlap_blocks, overlap_token_count = _create_overlap_blocks(
                current_chunk, overlap_tokens
            )
            
            current_chunk = overlap_blocks
            current_tokens = overlap_token_count
        
        current_chunk.append(block)
        current_tokens += block_tokens
    
    # Add the final chunk if it has content
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks



DEPTH_MAP_SAMPLE_TOKENS = 6000


def build_depth_map_prompt(blocks: List[TextBlock]) -> str:
    """
    Build the Pass-1 prompt that asks the LLM to infer the document's
    structural hierarchy *before* we ask it to classify individual elements.

    The output is a depth_map: a list of nesting depths (1..N) with the
    label/prefix pattern used at that depth and one concrete example. This
    map is then injected into the per-chunk extraction prompt so the model
    classifies by document-specific position rather than by guessing from
    surface cues like "1." vs "A.".
    """
    text_content = "\n".join(
        f"[Page {b.page_number}] {b.text}" for b in blocks
    )

    return f"""You are analyzing the structural skeleton of an early learning standards document. You will NOT extract individual elements — only the document's nesting hierarchy.

Read the sample below and identify how many distinct nesting depths the document uses, what each depth looks like (its prefix/label pattern), and one concrete example. The DEEPEST depth is always the leaf (individual learning goals/foundations/benchmarks).

This document's depths must then be mapped to a canonical 4-level hierarchy:
- depth 1 → "domain"
- depth 2 → "strand" (skip if the document has no level between domain and the groups that hold indicators)
- depth 3 → "sub_strand" (skip if absent)
- deepest depth → "indicator"

Rules:
- A 3-level document (domain > group > leaf) maps to: domain, sub_strand, indicator. There is NO strand.
- A 2-level document (domain > leaf) maps to: domain, indicator.
- Use depth POSITION, not the document's labels. If a document uses "Sub-Strand" as the label for the second level (directly under domain), it is still a STRAND in our canonical hierarchy.

Be deterministic and conservative. Do not speculate. If you cannot tell whether two depths are distinct, assume they are the same depth.

Output ONLY a JSON object with this exact shape:
{{
  "doc_depths": [
    {{"depth": 1, "canonical_level": "domain",     "label_in_doc": "<what the doc calls this>", "prefix_pattern": "<regex-ish pattern e.g. 'ALL-CAPS HEADING' or 'N. <Title>: <desc>'>", "example": "<exact text from doc>"}},
    {{"depth": 2, "canonical_level": "strand|sub_strand|indicator", ...}}
  ],
  "notes": "<one short sentence about anything unusual, e.g. age-band columns, sidebars to ignore>"
}}

DOCUMENT SAMPLE:

{text_content}"""


def build_detection_prompt(
    blocks: List[TextBlock],
    depth_map: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the Pass-2 per-chunk extraction prompt.

    If `depth_map` is provided (from build_depth_map_prompt + LLM), it is
    injected into the prompt so the model classifies by document-specific
    nesting depth rather than by re-inferring the hierarchy on every chunk.
    Pass `None` only for backwards compatibility / tests.
    """
    text_content = "\n".join(
        f"[Page {b.page_number}] {b.text}" for b in blocks
    )

    depth_map_block = (
        f"DEPTH MAP (authoritative — use this to assign `level`):\n"
        f"{json.dumps(depth_map, indent=2)}\n"
        if depth_map else
        "DEPTH MAP: not provided — infer the canonical level from nesting position, "
        "not from prefixes or labels.\n"
    )

    return f"""You extract structural elements from an early learning standards document chunk.

Be deterministic. Be conservative. Do not be creative. Two runs over the same text MUST produce the same JSON. Do not invent titles, codes, or descriptions — only use text that literally appears in the chunk.

CANONICAL HIERARCHY: domain (1) > strand (2) > sub_strand (3) > indicator (leaf). A document may skip strand or sub_strand; the depth map says which levels exist.

CLASSIFICATION RULE:
- If a depth map is provided, look up each element's depth in the document and use the `canonical_level` from that depth. Do NOT reclassify based on prefix style.
- If no depth map is provided, classify by nesting POSITION, never by what the document calls a level.

EXTRACTION RULES:
1. Emit every structural element you see, even if its children are not in this chunk.
2. A lettered/bulleted list (a., b., c., …) is EITHER the leaf indicators OR illustrative examples below a leaf — decide using the depth map, never the "a./b." surface style:
   - If the document's DEEPEST depth in the depth map is this lettered list (i.e. there is no deeper indicator level beneath the letters), then EACH lettered item IS an indicator. Emit one indicator per letter. Its `title` is the lettered item's own skill/competency statement (the text after the letter, e.g. "a. Demonstrates self-confidence." → "Demonstrates self-confidence"); any further example anecdotes indented beneath that letter go in its `description`. Do NOT fold these letters away and do NOT drop them — every lettered item in the chunk must appear.
   - Otherwise (the letters sit BELOW an already-identified leaf indicator and read as concrete behavior anecdotes, not skill statements) they are examples — fold them into the parent indicator's description or ignore them. Do NOT emit them as separate indicators.
3. Side-by-side age-band columns: emit ONE element PER column. Different age bands = different indicators, even when they share a code stem and title. Set `age_band` to the column label (e.g. "Early (3 to 4 ½ Years)", "PK3", "By 36 months"). Strip the age-band label from `title`. Put only that column's prose in `description`. If a row shows N age columns it MUST yield exactly N indicators — emit EVERY column even when a column's prose is short, nearly identical to its neighbor, or visually sparse. Never collapse or skip a column.
   - Spell each age-band label identically every time, using the document's exact glyphs (write "½", not "1/2").
4. `code`: use the document's code if present (e.g. "1.0", "I.A.2", "PK3.I.A.2"). Otherwise generate a stable ≤5-char uppercase abbreviation from the title — multi-word titles use the first letter of each word ("Physical Development" → "PHD", "Concepts About Print" → "CAP"), single-word titles use the first 4 letters ("Vocabulary" → "VOCA"). Use the SAME code every time the same element appears.
   - When a heading is written as `<Label> <id>: <Title>` — where `<Label>` is ANY structural word the document uses to name a level (e.g. Strand, Concept, Sub-Strand, Goal, Pillar, Unit, Theme, Section, Element, Standard, Domain, Benchmark, Component, Cluster, Foundation, Outcome, or whatever else this particular document uses) and `<id>` is the position identifier at that level (a number "1", a letter "A", a token "1.2") — the label-plus-id together is the element's `code` (e.g. "Strand 1", "Concept 2", "Goal A", "Pillar 1.2"). The `title` is ONLY the text after the colon (e.g. "Strand 1: Self-Awareness and Emotional Skills" → title "Self-Awareness and Emotional Skills"). This rule applies to EVERY structural-label heading word, not just the examples — never leave the `<Label> <id>:` prefix inside `title`, regardless of which word the document chose for `<Label>`.
   - The same principle holds when the structural label appears as a TRAILING noun on the heading instead of a prefix: a heading like `<Title> <Label>` (e.g. "Social and Emotional Development Domain", "Language and Literacy Standard", "Physical Development Area", "Number Sense Strand") names a `<Title>` of a level the document calls `<Label>`. The structural noun is the level word, NOT part of the name — emit only the bare `<Title>` ("Social and Emotional Development", "Language and Literacy", "Physical Development", "Number Sense"). This applies regardless of which structural noun the document uses (Domain, Standard, Area, Strand, Section, Component, Cluster, Foundation, etc.). The same-named element may also appear elsewhere on the page as a running page header in ALL CAPS (e.g. "SOCIAL EMOTIONAL DEVELOPMENT STANDARD" repeated at the top of every page) — that running header is page typography, not a separate element and not a code; if you emit anything for it, normalize it back to the same bare title-cased `<Title>` so the two variants share the SAME `code` and the SAME `title`. The abbreviation rule above ("≤5-char uppercase abbreviation from the title") still applies: derive the code from the BARE title (e.g. "Social Emotional Development" → "SED"), NEVER use the heading text itself or the structural noun as the code.
   - When a lettered list IS the leaf indicators (per rule 2), the `code` is JUST that item's letter, lowercased ("a", "b", "c", …) — exactly as the document orders them, regardless of any OCR casing. Do NOT prepend the parent strand/concept number (no "S1C1a"), and do NOT uppercase it (no bare "C"). The downstream parser supplies the parent's number; the detector only needs the consistent local letter.
5. `confidence`: 0.95+ if the depth map clearly applies; 0.80-0.94 if the chunk is ambiguous but the answer is likely; <0.70 if you are guessing.
6. `source_page`: page number from the [Page N] marker on that line.
7. `source_text`: the exact line(s) from the chunk you used. Copy verbatim.
8. `description`: capture the element's COMPLETE descriptive/introductory prose, verbatim — EVERY sentence of a domain/strand/sub_strand introduction that appears in the chunk, not just the first sentence. Do NOT summarize, paraphrase, shorten, or stop at the first sentence. If the intro runs across several sentences or lines in the chunk, include all of them. (For an age-band column indicator, `description` is still only that one column's prose, per rule 3.)

NEGATIVE EXAMPLES (do NOT do these):
- Do not emit "Indicators and Examples in the Context of Daily Routines" as a structural element. It is a section header for examples.
- Do not merge "Early" and "Later" age columns into one indicator.
- Do not keep a structural label inside the title: "Strand 1: Self-Awareness" → title is "Self-Awareness", NOT "Strand 1: Self-Awareness".
- Do not keep a trailing structural noun inside the title: "Social and Emotional Development Domain" → title is "Social and Emotional Development", NOT "Social and Emotional Development Domain". "Language and Literacy Standard" → title is "Language and Literacy".
- Do not classify a numeric prefix ("1.", "2.") as `sub_strand` just because numeric-under-letter is sub_strand in some other doc — use the depth map.
- Do not truncate a multi-sentence domain/strand description to its first sentence — capture the entire introduction verbatim.
- When the depth map's leaf is a lettered list, do NOT drop or fold its letters: every "a./b./c." skill statement under a concept is its own indicator (e.g. under "Phonological Awareness" emit indicators "a","b","c","d","e","f","g", one per letter). Emit them even for concepts whose letters appear far from the concept heading in the chunk.
- When a lettered list is NOT the leaf — concrete anecdotes ("Chooses carrots over celery during mealtime.") sitting under an already-identified leaf indicator/foundation — do NOT promote them to indicators; fold them into that indicator's description.

OUTPUT — return ONLY a JSON array, starting with `[` and ending with `]`. No prose, no markdown, no commentary. Schema per element:
{{"level": "domain|strand|sub_strand|indicator", "code": "...", "title": "...", "description": "...", "age_band": "..." or null, "confidence": 0.0-1.0, "source_page": N, "source_text": "..."}}

{depth_map_block}
DOCUMENT CHUNK:

{text_content}"""


def _sample_blocks_for_depth_map(
    blocks: List[TextBlock],
    target_tokens: int = DEPTH_MAP_SAMPLE_TOKENS,
) -> List[TextBlock]:
    """Sample evenly across the document so depth_map sees structure from
    beginning, middle, and end (TOC pages, body, appendix all differ)."""
    if not blocks:
        return []
    total_tokens = sum(estimate_tokens(b.text) for b in blocks)
    if total_tokens <= target_tokens:
        return blocks
    # Take a contiguous middle slice — mid-document is usually the cleanest
    # repeat of the structural pattern (TOC and appendices are noisy).
    stride = max(1, total_tokens // target_tokens)
    sampled, tokens = [], 0
    for i, b in enumerate(blocks):
        if i % stride == 0:
            sampled.append(b)
            tokens += estimate_tokens(b.text)
            if tokens >= target_tokens:
                break
    return sampled


def infer_depth_map(
    blocks: List[TextBlock],
    metrics_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pass 1: ask the LLM to describe the document's nesting hierarchy.

    Returns the parsed depth_map dict, or None on failure (caller should
    fall back to no-depth-map mode rather than aborting detection).
    """
    sample = _sample_blocks_for_depth_map(blocks)
    if not sample:
        return None

    prompt = build_depth_map_prompt(sample)
    logger.info(
        f"Inferring depth map from {len(sample)} sampled blocks "
        f"(~{sum(estimate_tokens(b.text) for b in sample)} tokens)"
    )

    try:
        response_text = call_bedrock_llm(prompt, metrics_context=metrics_context, model_id=Config.BEDROCK_DEPTH_MAP_LLM_MODEL_ID)
    except Exception as e:
        logger.warning(f"Depth-map inference failed at Bedrock call: {e}")
        return None

    # The response is a single JSON OBJECT, not an array.
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines[1:] if not l.strip().startswith("```")).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or start >= end:
        logger.warning(f"Depth-map response was not a JSON object: {text[:300]}")
        return None
    try:
        depth_map = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Depth-map JSON parse failed: {e}")
        return None

    if not isinstance(depth_map, dict) or "doc_depths" not in depth_map:
        logger.warning(f"Depth-map missing required key 'doc_depths': {depth_map}")
        return None

    logger.info(f"Depth map inferred: {len(depth_map['doc_depths'])} levels")
    for d in depth_map["doc_depths"]:
        logger.info(
            f"  depth={d.get('depth')} → {d.get('canonical_level')} "
            f"(pattern: {d.get('prefix_pattern')!r})"
        )
    return depth_map



def _extract_json_from_response(response_text: str) -> str:
    """
    Extract JSON array from LLM response text.
    
    The LLM may sometimes include extra text before or after the JSON.
    This function extracts just the JSON array portion.
    
    Args:
        response_text: Raw response text from LLM
        
    Returns:
        Extracted JSON string
        
    Raises:
        ValueError: If no valid JSON array is found
    """
    response_text = response_text.strip()
    
    # Strip markdown code fences if present (e.g. ```json ... ```)
    if response_text.startswith("```"):
        lines = response_text.splitlines()
        # Drop the opening fence line and any closing fence
        response_text = "\n".join(
            line for line in lines[1:]
            if not line.strip().startswith("```")
        ).strip()
    
    logger.debug(f"Extracting JSON from response of length {len(response_text)}")
    
    # Find JSON array boundaries
    start_idx = response_text.find('[')
    end_idx = response_text.rfind(']')
    
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        logger.error(f"No valid JSON array found. Response text: {response_text[:1000]}")
        raise ValueError("No valid JSON array found in response")
    
    json_str = response_text[start_idx:end_idx + 1]
    logger.debug(f"Extracted JSON string of length {len(json_str)}")
    
    return json_str


def _validate_element_data(elem_data: Dict[str, Any]) -> Optional[str]:
    """
    Validate element data has all required fields.
    
    Args:
        elem_data: Dictionary containing element data
        
    Returns:
        Error message if validation fails, None if valid
    """
    required_fields = ['level', 'code', 'title', 'description', 'confidence', 'source_page', 'source_text']
    missing_fields = [field for field in required_fields if field not in elem_data]
    
    if missing_fields:
        return f"Missing required fields: {missing_fields}"
    
    return None


def _normalize_age_band(age_band: Any) -> Optional[str]:
    """
    Canonicalize an age-band label so the same band is spelled identically
    every time. The LLM transcribes the half-year glyph inconsistently —
    unicode '½' vs ASCII '1/2' — which otherwise produces two distinct
    age_band strings for the same column (e.g. "Early (3 to 4 ½ Years)" and
    "Early (3 to 4 1/2 Years)"). We fold ASCII to the unicode glyph (matching
    the source PDFs) and collapse whitespace.
    """
    if not isinstance(age_band, str):
        return None
    normalized = " ".join(age_band.split()).replace("1/2", "½")
    return normalized or None


def _strip_label_prefix(title: Any) -> Any:
    """Strip trailing footnote/reference markers ("…rules.*", "…health †") —
    typography the LLM transcribes inconsistently across runs. Removing them
    keeps a title byte-stable so it matches the golden's marker-free title.
    No-op for titles that already lack a marker. Never strips the title down to
    empty: if cleaning would leave nothing, the original is kept."""
    if not isinstance(title, str):
        return title
    cleaned = _TRAILING_MARKER_RE.sub("", title).strip()
    return cleaned or title


def _create_detected_element(elem_data: Dict[str, Any], default_page: int) -> Optional[DetectedElement]:
    """
    Create a DetectedElement from validated element data.
    
    Args:
        elem_data: Dictionary containing element data
        default_page: Default page number if source_page is invalid
        
    Returns:
        DetectedElement object, or None if creation fails
    """
    try:
        # Validate and convert level
        level = HierarchyLevelEnum(elem_data['level'])
    except ValueError:
        logger.warning(f"Invalid hierarchy level '{elem_data['level']}', skipping element")
        return None
    
    # Ensure confidence is in valid range [0.0, 1.0]
    confidence = float(elem_data['confidence'])
    confidence = max(0.0, min(1.0, confidence))
    
    # Determine needs_review based on confidence threshold
    needs_review = confidence < Config.CONFIDENCE_THRESHOLD
    
    age_band = _normalize_age_band(elem_data.get('age_band'))

    title = _strip_label_prefix(elem_data['title'])
    # Indicator titles are full sentences transcribed from the source, so the LLM
    # keeps the terminal period ("…diseases."). The canonical form drops it — the
    # golden indicator titles are authored period-free. Scope this to indicators:
    # domain/strand/sub_strand titles are short noun-phrase labels with no
    # terminal punctuation, so they're left untouched.
    if level == HierarchyLevelEnum.INDICATOR and isinstance(title, str):
        title = title.rstrip().rstrip('.').rstrip() or title

    return DetectedElement(
        level=level,
        code=elem_data['code'],
        title=title,
        description=elem_data.get('description') or "",
        confidence=confidence,
        source_page=elem_data.get('source_page', default_page),
        source_text=elem_data['source_text'],
        needs_review=needs_review,
        age_band=age_band,
    )


def parse_llm_response(response_text: str, blocks: List[TextBlock]) -> List[DetectedElement]:
    """
    Parse LLM response into DetectedElement objects.
    
    This function handles various edge cases including:
    - Extra text around the JSON array
    - Missing or invalid fields
    - Invalid hierarchy levels
    - Out-of-range confidence values
    
    Args:
        response_text: Raw response text from LLM
        blocks: Original text blocks (for fallback page numbers)
        
    Returns:
        List of DetectedElement objects (may be empty if parsing fails)
        
    Raises:
        json.JSONDecodeError: If response is not valid JSON
        ValueError: If response structure is invalid
    """
    logger.debug("Parsing LLM response")
    
    # Extract JSON from response
    json_text = _extract_json_from_response(response_text)
    elements_data = json.loads(json_text)
    
    if not isinstance(elements_data, list):
        logger.error(f"Response is not a JSON array, got type: {type(elements_data)}")
        raise ValueError("Response must be a JSON array")
    
    logger.info(f"Parsed {len(elements_data)} elements from LLM response")
    
    detected_elements = []
    default_page = blocks[0].page_number if blocks else 1
    
    for idx, elem_data in enumerate(elements_data):
        # Validate required fields
        validation_error = _validate_element_data(elem_data)
        if validation_error:
            logger.warning(f"Element {idx}: {validation_error}, skipping element")
            continue
        
        # Create detected element
        element = _create_detected_element(elem_data, default_page)
        if element:
            detected_elements.append(element)
            logger.debug(
                f"Element {idx}: {element.level.value} - {element.code} - "
                f"{element.title[:50]} (confidence: {element.confidence:.2f})"
            )
        else:
            logger.warning(f"Element {idx}: Failed to create DetectedElement")
    
    logger.info(f"Successfully created {len(detected_elements)} DetectedElement objects")
    
    return detected_elements


def _build_bedrock_request(
    prompt: str,
    prefill: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build request body for Bedrock Claude API.

    `prefill` is appended as an assistant message — Claude continues from it
    verbatim, which is the most reliable way to force a structured-output
    format (e.g. `[` to force a JSON array) on Opus 4.7 where we cannot
    set `temperature`.

    `temperature` (when not None) pins sampling — we pass 0 on models that
    still accept it (Opus 4.6, Haiku 4.5) so detection is as deterministic as
    the model allows; the caller drops it for models that reject sampling
    params (Opus 4.7/4.8, Fable).
    """
    messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    if prefill:
        messages.append({"role": "assistant", "content": prefill})
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LLM_MAX_TOKENS,
        "messages": messages,
    }
    if temperature is not None:
        body["temperature"] = temperature
    return body


def _extract_text_from_bedrock_response(response_body: Dict[str, Any]) -> str:
    """
    Extract text content from Bedrock Claude response.
    
    Args:
        response_body: Parsed response body from Bedrock
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If response format is unexpected
    """
    if 'content' not in response_body or len(response_body['content']) == 0:
        raise ValueError("Unexpected response format from Bedrock: missing content")
    
    return response_body['content'][0]['text']


def call_bedrock_llm(
    prompt: str,
    max_retries: int = MAX_BEDROCK_RETRIES,
    metrics_context: Optional[Dict[str, Any]] = None,
    prefill: Optional[str] = None,
    model_id: Optional[str] = None,
) -> str:
    """
    Call Amazon Bedrock LLM (Claude) with the given prompt.
    
    Implements retry logic for transient failures like throttling.
    Captures and emits token usage and latency metrics.
    
    Args:
        prompt: The prompt to send to the LLM
        max_retries: Maximum number of retry attempts (default: 2)
        metrics_context: Optional dict with run_id, country, state,
                         batch_index, chunk_index for metric dimensions
        
    Returns:
        LLM response text
        
    Raises:
        ClientError: If Bedrock API call fails after all retries
        ValueError: If response format is unexpected
    """
    bedrock = boto3.client(
        'bedrock-runtime',
        region_name=Config.AWS_REGION,
        config=BotocoreConfig(
            read_timeout=300,   # 5 minutes — Claude can be slow with large outputs
            connect_timeout=10,
            retries={"max_attempts": 0}  # We handle retries ourselves
        )
    )
    ctx = metrics_context or {}
    effective_model_id = model_id or Config.BEDROCK_DETECTOR_LLM_MODEL_ID
    # Opus 4.6 (and cross-region variants) does not support assistant prefill.
    if prefill and "opus-4-6" in effective_model_id:
        logger.debug(f"Dropping prefill — model {effective_model_id} does not support it")
        prefill = None
    # Pin temperature for determinism, but only on models that accept it.
    temperature: Optional[float] = LLM_TEMPERATURE
    if any(m in effective_model_id for m in _TEMPERATURE_UNSUPPORTED):
        logger.debug(f"Dropping temperature — model {effective_model_id} rejects sampling params")
        temperature = None
    request_body = _build_bedrock_request(prompt, prefill=prefill, temperature=temperature)

    logger.info(f"Calling Bedrock with model: {effective_model_id}")
    logger.debug(f"Prompt length: {len(prompt)} characters, ~{estimate_tokens(prompt)} tokens")

    for attempt in range(max_retries + 1):
        try:
            with MetricsTimer() as timer:
                response = bedrock.invoke_model(
                    modelId=effective_model_id,
                    body=json.dumps(request_body)
                )
                response_body = json.loads(response['body'].read())
            
            response_text = _extract_text_from_bedrock_response(response_body)
            # Bedrock returns only Claude's continuation; if we prefilled,
            # re-prepend it so downstream parsing sees a complete document.
            if prefill:
                response_text = prefill + response_text
            usage = extract_usage_from_response(response_body)
            
            # Emit metrics
            call_metrics = LLMCallMetrics(
                stage="detection",
                model_id=effective_model_id,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                latency_ms=timer.elapsed_ms,
                retry_count=attempt,
                run_id=ctx.get("run_id", ""),
                country=ctx.get("country", ""),
                state=ctx.get("state", ""),
                batch_index=ctx.get("batch_index"),
                chunk_index=ctx.get("chunk_index"),
                success=True,
            )
            log_llm_call_metrics(call_metrics)
            emit_cloudwatch_metrics(call_metrics)
            
            logger.info(
                f"Bedrock response received: {len(response_text)} chars, "
                f"{usage['input_tokens']} in / {usage['output_tokens']} out tokens, "
                f"{timer.elapsed_ms:.0f}ms"
            )
            
            return response_text
                
        except ClientError as e:
            if attempt < max_retries:
                logger.warning(
                    f"Bedrock API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                continue
            else:
                # Emit error metrics
                error_metrics = LLMCallMetrics(
                    stage="detection",
                    model_id=effective_model_id,
                    retry_count=attempt,
                    run_id=ctx.get("run_id", ""),
                    country=ctx.get("country", ""),
                    state=ctx.get("state", ""),
                    success=False,
                    error=str(e),
                )
                log_llm_call_metrics(error_metrics)
                emit_cloudwatch_metrics(error_metrics)
                
                logger.error(
                    f"Bedrock API call failed after {max_retries + 1} attempts: {e}"
                )
                raise
        except ValueError as e:
            logger.error(f"Invalid Bedrock response format: {e}")
            raise
    
    raise RuntimeError("Failed to get response from Bedrock after all retries")


def _process_chunk(
    chunk: List[TextBlock],
    chunk_idx: int,
    total_chunks: int,
    depth_map: Optional[Dict[str, Any]] = None,
) -> List[DetectedElement]:
    """
    Process a single chunk of text blocks through the LLM.
    
    Implements retry logic for JSON parsing failures.
    
    Args:
        chunk: Text blocks to process
        chunk_idx: Index of this chunk (for logging)
        total_chunks: Total number of chunks (for logging)
        
    Returns:
        List of detected elements from this chunk
    """
    logger.info(
        f"Processing chunk {chunk_idx + 1}/{total_chunks} "
        f"({len(chunk)} blocks, ~{sum(estimate_tokens(b.text) for b in chunk)} tokens)"
    )
    
    # Build prompt for this chunk
    prompt = build_detection_prompt(chunk, depth_map=depth_map)

    # Try to parse LLM response with retries
    for parse_attempt in range(MAX_PARSE_RETRIES + 1):
        try:
            response_text = call_bedrock_llm(prompt)
            
            # Parse response
            elements = parse_llm_response(response_text, chunk)
            
            logger.info(
                f"Chunk {chunk_idx + 1}/{total_chunks}: Successfully detected "
                f"{len(elements)} elements"
            )
            
            return elements
            
        except (json.JSONDecodeError, ValueError) as e:
            if parse_attempt < MAX_PARSE_RETRIES:
                logger.warning(
                    f"Chunk {chunk_idx + 1}/{total_chunks}: Failed to parse LLM response "
                    f"(attempt {parse_attempt + 1}/{MAX_PARSE_RETRIES + 1}): {e}"
                )
                # Retry with the same prompt
                continue
            else:
                logger.error(
                    f"Chunk {chunk_idx + 1}/{total_chunks}: Failed to parse LLM response "
                    f"after {MAX_PARSE_RETRIES + 1} attempts: {e}"
                )
                # Return empty list rather than failing entire detection
                return []
    
    return []


def _dedup_elements(elements: List[DetectedElement]) -> List[DetectedElement]:
    """
    Drop duplicate elements produced by chunk overlap.

    Adjacent chunks intentionally overlap (DEFAULT_OVERLAP_TOKENS) so elements
    at a chunk boundary can be re-emitted by both chunks. Collapse those on a
    content key of (level, normalized title, age_band, source_page), keeping
    the highest-confidence instance. Order is preserved by first appearance so
    the document-ordered structure (and downstream domain context) is intact.
    """
    best: Dict[tuple, DetectedElement] = {}
    order: List[tuple] = []
    for el in elements:
        key = (
            el.level.value,
            " ".join((el.title or "").lower().split()),
            el.age_band or None,
            el.source_page,
        )
        if key not in best:
            best[key] = el
            order.append(key)
        elif el.confidence > best[key].confidence:
            best[key] = el
    deduped = [best[k] for k in order]
    dropped = len(elements) - len(deduped)
    if dropped:
        logger.info(f"De-duplicated {dropped} overlap-repeated elements "
                    f"({len(elements)} → {len(deduped)})")
    return deduped


def detect_structure(blocks: List[TextBlock], document_s3_key: str = "") -> DetectionResult:
    """
    Detect hierarchical structure in extracted text blocks using Claude Sonnet 4.5.
    
    This function:
    1. Chunks text blocks into manageable sizes with overlap
    2. Sends each chunk to Claude Sonnet 4.5 for structure detection
    3. Parses and validates the LLM responses
    4. Flags low-confidence elements for review
    5. Aggregates results across all chunks
    
    The function is resilient to:
    - Malformed LLM responses (with retry)
    - Missing or invalid fields
    - Bedrock API failures (with retry)
    
    Args:
        blocks: List of text blocks from text extraction
        document_s3_key: S3 key of the source document (for tracking)
        
    Returns:
        DetectionResult with detected elements, review count, and status
    """
    logger.info(f"Starting structure detection for document: {document_s3_key}")
    logger.info(f"Input: {len(blocks)} text blocks")
    
    if not blocks:
        logger.error("No text blocks provided")
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            review_count=0,
            status="error",
            error="No text blocks provided"
        )
    
    try:
        # Pass 1: infer the document's nesting hierarchy. We pass it into
        # every per-chunk extraction so the model classifies by document
        # depth rather than re-guessing on each chunk.
        depth_map = infer_depth_map(blocks)
        if depth_map is None:
            logger.warning(
                "Depth-map inference failed; falling back to no-depth-map mode"
            )

        # Pass 2: chunk and extract.
        chunks = chunk_text_blocks(blocks)
        logger.info(
            f"Created {len(chunks)} chunks from {len(blocks)} text blocks "
            f"(target: {DEFAULT_TARGET_TOKENS} tokens, overlap: {DEFAULT_OVERLAP_TOKENS} tokens)"
        )

        all_elements = []

        for chunk_idx, chunk in enumerate(chunks):
            chunk_elements = _process_chunk(
                chunk, chunk_idx, len(chunks), depth_map=depth_map
            )
            all_elements.extend(chunk_elements)
            
            logger.info(
                f"Progress: {chunk_idx + 1}/{len(chunks)} chunks processed, "
                f"{len(all_elements)} total elements detected so far"
            )

        # Collapse elements re-emitted at overlapping chunk boundaries.
        all_elements = _dedup_elements(all_elements)

        # Count elements needing review
        review_count = sum(1 for elem in all_elements if elem.needs_review)
        
        # Log summary by level
        level_counts = {}
        for elem in all_elements:
            level_counts[elem.level.value] = level_counts.get(elem.level.value, 0) + 1
        
        logger.info(
            f"Detection complete: {len(all_elements)} total elements detected"
        )
        logger.info(f"Elements by level: {level_counts}")
        logger.info(
            f"Review needed: {review_count} elements "
            f"(confidence < {Config.CONFIDENCE_THRESHOLD})"
        )
        
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=all_elements,
            review_count=review_count,
            status="success",
            error=None
        )
        
    except Exception as e:
        logger.error(f"Structure detection failed: {e}", exc_info=True)
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            review_count=0,
            status="error",
            error=str(e)
        )
