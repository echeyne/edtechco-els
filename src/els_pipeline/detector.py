"""Structure detection module for ELS pipeline."""

import json
import logging
from typing import List, Dict, Any, Optional
import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError

from .models import TextBlock, DetectedElement, DetectionResult, HierarchyLevelEnum
from .config import Config

logger = logging.getLogger(__name__)

# Constants
CHARS_PER_TOKEN = 4
DEFAULT_TARGET_TOKENS = 2000
DEFAULT_OVERLAP_TOKENS = 500
MAX_PARSE_RETRIES = 2
MAX_BEDROCK_RETRIES = 2
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 16000


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



def build_detection_prompt(blocks: List[TextBlock]) -> str:
    """
    Build a structured prompt for the LLM to detect hierarchy elements.

    The prompt is designed to extract educational standards hierarchy from
    early learning standards documents, identifying domains, strands,
    sub_strands, and indicators with their associated metadata.

    Args:
        blocks: List of text blocks to analyze

    Returns:
        Formatted prompt string optimized for Claude Sonnet 4.5
    """
    # Combine text blocks with page numbers for context
    text_content = "\n".join([
        f"[Page {block.page_number}] {block.text}"
        for block in blocks
    ])

    prompt = f"""You are extracting the hierarchical structure from an early learning standards document. Your job is to identify every structural element and classify it into the correct hierarchy level.

STRICT RULE: You must use ONLY the exact titles, codes (as applicable), numbers, and names that appear in the document text. Do NOT invent any titles. If a code does not exist in the document, generate a short uppercase abbreviation from the title (e.g. "Physical Development" → "PHD", "Social Emotional" → "SE"). Use at most 5 characters. Be consistent: if you assign a code to an element, use that EXACT same code every time that element appears.

HIERARCHY LEVELS (from highest to lowest):
Our normalized hierarchy has exactly four levels. Every document must be mapped into these four levels:
1. "domain" — The broadest category (nesting depth 1). The top-level developmental areas that contain everything else.
2. "strand" — The second level of grouping (nesting depth 2). A grouping that sits directly under a domain and contains sub_strands or indicators beneath it.
3. "sub_strand" — The third level (nesting depth 3). A grouping that sits under a strand (or directly under a domain if no strand exists) and contains indicators beneath it.
4. "indicator" — The leaf level (nesting depth 4, or the deepest level present). Individual learning goals, foundations, benchmarks, or skill statements. These describe what a child should know or be able to do. They do NOT contain other structural elements beneath them. IMPORTANT: An indicator is the learning goal statement itself (e.g., "The child demonstrates an awareness of self."), NOT the lettered/bulleted examples or observable behaviors listed beneath it. Those examples illustrate the indicator but are not separate indicators.

CRITICAL — CLASSIFY BY NESTING DEPTH, NOT BY DOCUMENT LABELS:
Different states use different terminology. A document may call something a "Sub-Strand" but if it sits at the second nesting level (directly under a domain, with further groupings beneath it), it is a STRAND in our hierarchy. Similarly, a document may call something a "Topic" but if it is the third nesting level, it is a SUB_STRAND.

Follow this process:
1. FIRST, read the entire text and identify the document's own structural hierarchy. Map out how many nesting levels exist and what sits under what.
2. THEN, map each nesting level to our four-level hierarchy based on POSITION, not labels:
   - The topmost grouping (the broadest category that contains everything else) → "domain"
   - The next level down (groups that sit directly inside a domain and contain further sub-groups or indicators) → "strand"
   - The next level down (groups that contain indicators) → "sub_strand"
   - The leaf-level items (specific learning statements, foundations, benchmarks, skills) → "indicator"
3. If the document only has 3 nesting levels (no intermediate grouping between domain and the groups that hold indicators), then there are no strands — map the groups directly under the domain as "sub_strand" and their children as "indicator".
4. If the document has 4+ nesting levels, collapse the deeper levels as needed so everything fits into our four-level model.

CRITICAL — INDICATORS vs. EXAMPLES/EVIDENCE:
Many early learning standards documents list "Indicators and Examples" or "Examples in the Context of Daily Routines, Activities, and Play" beneath a learning goal statement. These lettered or bulleted items (e.g., "a. Demonstrates self-confidence", "b. Makes personal preferences known to others") are NOT separate indicators. They are illustrative examples or observable behaviors that help teachers recognize the indicator in practice.

The actual INDICATOR is the overarching learning goal statement that appears ABOVE these examples, such as "The child demonstrates an awareness of self." The description paragraph that follows it (e.g., "Children develop a sense of personal identity as they begin to recognize the characteristics that make them unique as individuals and to build self-esteem.") is the indicator's description.

When you encounter this pattern:
- The learning goal statement (e.g., "The child demonstrates an awareness of self.") → this is the INDICATOR title
- The explanatory paragraph below it → this is the INDICATOR description
- The lettered/bulleted examples beneath (a, b, c, d, e...) with their sub-bullets → these are NOT separate indicators. Do NOT extract them as indicators. They are supporting examples and should be IGNORED as structural elements. You may optionally include them as part of the indicator's description text, but they must NOT be emitted as their own elements.

Similarly, sections labeled "Indicators and Examples in the Context of Daily Routines, Activities, and Play" are section headers for the examples area — they are NOT indicators themselves.

EXAMPLES OF LABEL-TO-LEVEL MAPPING (these are illustrative, not exhaustive):
- A document labels top sections as "Domains" and has "Strands" under them, with "Sub-Strands" under those, and "Foundations" at the bottom:
  → Domain = domain, Strand = strand, Sub-Strand = sub_strand, Foundation = indicator
- A document labels top sections as "Areas" with "Goals" under them and "Objectives" under those:
  → Area = domain, Goal = strand, Objective = indicator (no sub_strand)
- A document labels top sections as "Domains" with "Standards" directly containing "Indicators":
  → Domain = domain, Standard = sub_strand (no strand), Indicator = indicator
- A document has a developmental area (e.g., "Social Emotional Development"), then "Strands" (e.g., "Self-Awareness and Emotional Skills"), then "Concepts" (e.g., "Self-Awareness"), then a learning goal statement (e.g., "The child demonstrates an awareness of self.") followed by lettered examples (a, b, c...):
  → Developmental area = domain, Strand = strand, Concept = sub_strand, Learning goal statement = indicator. The lettered examples are NOT indicators — they are illustrative examples and should be excluded or folded into the indicator description.

CRITICAL — SIDE-BY-SIDE AGE-GROUP OUTCOMES ARE SEPARATE INDICATORS:
Some documents present outcomes for different age groups (e.g., PK3 and PK4, "Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)", "By 36 months", "By 48 months") in side-by-side table columns. Each column represents a DISTINCT indicator and MUST be extracted as its own separate element. Do NOT merge them into a single indicator.

For example, if you see a table with a "PK3 Outcome" column and a "PK4 Outcome" column:
- "PK3.I.A.2 Child can identify own physical attributes and indicate some likes and dislikes when prompted." → one indicator with code "PK3.I.A.2"
- "PK4.I.A.2 Child shows self-awareness of physical attributes, personal preferences, and own abilities." → a SEPARATE indicator with code "PK4.I.A.2"

These are NOT the same indicator. They have different codes, different titles, and different descriptions. The fact that they appear on the same row or page does not make them one element. Always emit one JSON object per age-group outcome.

FIELD INSTRUCTIONS:
- "level": One of "domain", "strand", "sub_strand", or "indicator".
- "code": The code or number from the document (e.g., "1.0", "1.1", "ATL"). If the document does not assign a code, generate a short uppercase abbreviation from the title (max 5 characters, e.g. "Physical Development" → "PHD"). Do NOT use the full title or a camelCase version of the title as the code.
- "title": The exact title as written in the document. Only shorten it if it has redundent leading/trailing text like "STRAND" or "DOMAIN". IMPORTANT: Strip age-band pre-text labels from indicator titles. Remove prefixes like "Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)", "By 36 months", "By 48 months", "Younger Toddler", "Older Toddler", "PK3", "PK4", etc. The title should be the actual name of the indicator, not the age-band label. For example, if the document shows "Early (3 to 4 ½ Years)" as a label above the indicator text "Curiosity and Interest", the title should be "Curiosity and Interest", NOT "Early (3 to 4 ½ Years)". The age-band information should go into the age_band field instead.
- "description": The full descriptive text associated with this element, including any age-band details. Combine all age-specific text into one description. If there is no description beyond the title, use an empty string "".
- "confidence": A float between 0.0 and 1.0 reflecting how certain you are about the classification:
  - 0.95+ : Nesting position is unambiguous and the element clearly maps to this level.
  - 0.85-0.94 : Nesting position is clear but the document's labeling is somewhat ambiguous.
  - 0.70-0.84 : The nesting structure has some ambiguity (e.g., unclear if a level should be strand or sub_strand).
  - Below 0.70 : Uncertain classification.
- "source_page": The page number from the [Page N] marker where this element appears.
- "source_text": The exact text from the document that you used to identify this element. Copy it verbatim.

OUTPUT FORMAT — Return ONLY a JSON array. No text before or after it.
[
  {{
    "level": "domain|strand|sub_strand|indicator",
    "code": "exact code from document or empty string",
    "title": "exact title from document",
    "description": "full description from document including age-specific details",
    "confidence": 0.95,
    "source_page": 1,
    "source_text": "exact text copied from document"
  }}
]

CRITICAL — ELEMENTS THAT SPAN PAGE BOUNDARIES:
Documents are chunked for processing, so you may see structural elements whose children appear in a DIFFERENT chunk. This is normal and expected. You MUST still extract these elements. Specifically:
- If you see a strand or sub_strand header (e.g., "C. Relationships with Others") with a description paragraph but NO indicators beneath it in this text, extract it anyway. Its indicators will appear in a later chunk.
- If you see indicators that appear to belong to a strand/sub_strand not shown in this text, extract the indicators. The parent element was in a previous chunk.
- Do NOT skip an element just because it has no children visible in the current text. Every heading, section title, or structural marker must be extracted regardless of whether its children are present.

CRITICAL — RECOGNIZING LESS OBVIOUS HIERARCHY MARKERS:
Not all structural elements are formatted with bold headings or numbered lists. Watch for these patterns:
- A lettered section (e.g., "A. Self-Concept", "B. Self-Regulation", "C. Relationships with Others") followed by a descriptive paragraph is a structural element, even if it appears at the very end of the text with nothing after it.
- A numbered sub-section (e.g., "1. Behavior Control", "2. Emotional Control") under a lettered section is also a structural element.
- Section headers may appear in different visual styles: bold, colored, larger font, or simply as a line starting with a letter/number prefix. The text extraction may not preserve formatting, so rely on the alphanumeric prefix pattern (A., B., C., 1., 2., 3.) and the presence of a descriptive paragraph to identify structural elements.
- A standalone line that looks like a title (short, no period at the end, followed by a longer descriptive paragraph) is likely a structural element even without an explicit letter/number prefix.

FINAL REMINDERS:
- Return ONLY the JSON array. No markdown, no explanation, no commentary.
- Extract EVERY structural element you find. Do not skip any — even if it appears at the very end of the text with no children visible.
- Use the page numbers from the [Page N] markers in the text.
- Remember: classify by NESTING DEPTH in the document, NOT by what the document calls each level.

TEXT TO ANALYZE:

{text_content}"""

    return prompt



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
    
    return DetectedElement(
        level=level,
        code=elem_data['code'],
        title=elem_data['title'],
        description=elem_data['description'],
        confidence=confidence,
        source_page=elem_data.get('source_page', default_page),
        source_text=elem_data['source_text'],
        needs_review=needs_review
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


def _build_bedrock_request(prompt: str) -> Dict[str, Any]:
    """
    Build request body for Bedrock Claude API.
    
    Args:
        prompt: The prompt to send to the LLM
        
    Returns:
        Request body dictionary
    """
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": LLM_TEMPERATURE  # Low temperature for consistent structured output
    }


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


def call_bedrock_llm(prompt: str, max_retries: int = MAX_BEDROCK_RETRIES) -> str:
    """
    Call Amazon Bedrock LLM (Claude Sonnet 4.5) with the given prompt.
    
    Implements retry logic for transient failures like throttling.
    Uses Claude Sonnet 4.5 for optimal performance on structured extraction tasks.
    
    Args:
        prompt: The prompt to send to the LLM
        max_retries: Maximum number of retry attempts (default: 2)
        
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
    request_body = _build_bedrock_request(prompt)
    
    logger.info(f"Calling Bedrock with model: {Config.BEDROCK_DETECTOR_LLM_MODEL_ID}")
    logger.debug(f"Prompt length: {len(prompt)} characters, ~{estimate_tokens(prompt)} tokens")
    
    for attempt in range(max_retries + 1):
        try:
            response = bedrock.invoke_model(
                modelId=Config.BEDROCK_DETECTOR_LLM_MODEL_ID,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            response_text = _extract_text_from_bedrock_response(response_body)
            
            logger.info(f"Bedrock response received: {len(response_text)} characters")
            logger.debug(f"Response preview: {response_text[:500]}...")
            
            return response_text
                
        except ClientError as e:
            if attempt < max_retries:
                logger.warning(
                    f"Bedrock API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                continue
            else:
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
    total_chunks: int
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
    prompt = build_detection_prompt(chunk)
    
    # Try to parse LLM response with retries
    for parse_attempt in range(MAX_PARSE_RETRIES + 1):
        try:
            # Call Bedrock
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
        # Chunk the text blocks
        chunks = chunk_text_blocks(blocks)
        logger.info(
            f"Created {len(chunks)} chunks from {len(blocks)} text blocks "
            f"(target: {DEFAULT_TARGET_TOKENS} tokens, overlap: {DEFAULT_OVERLAP_TOKENS} tokens)"
        )
        
        all_elements = []
        
        # Process each chunk
        for chunk_idx, chunk in enumerate(chunks):
            chunk_elements = _process_chunk(chunk, chunk_idx, len(chunks))
            all_elements.extend(chunk_elements)
            
            logger.info(
                f"Progress: {chunk_idx + 1}/{len(chunks)} chunks processed, "
                f"{len(all_elements)} total elements detected so far"
            )
        
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
