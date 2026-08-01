"""Text extraction module using AWS Textract."""

import logging
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

from .models import TextBlock, ExtractionResult
from .config import Config

logger = logging.getLogger(__name__)


def extract_text(s3_key: str, s3_version_id: str) -> ExtractionResult:
    """
    Extract text from a document stored in S3 using AWS Textract.
    
    Args:
        s3_key: S3 key of the document
        s3_version_id: S3 version ID of the document
        
    Returns:
        ExtractionResult containing extracted text blocks or error information
    """
    try:
        textract_client = boto3.client('textract', region_name=Config.AWS_REGION)
        
        # Synchronous AnalyzeDocument only supports single-page documents (images).
        # PDFs can be multi-page even when small, so always use async for them.
        is_pdf = s3_key.lower().endswith('.pdf')
        if is_pdf:
            textract_response = _extract_async(textract_client, s3_key, s3_version_id)
        else:
            # Images (JPEG, PNG, TIFF) are single-page, safe for sync
            textract_response = _extract_sync(textract_client, s3_key, s3_version_id)
        
        if not textract_response:
            logger.error(f"Textract extraction failed for {s3_key}")
            return ExtractionResult(
                document_s3_key=s3_key,
                blocks=[],
                total_pages=1,
                status="error",
                error="Textract extraction failed"
            )
        
        # Parse Textract response into TextBlock objects
        blocks = _parse_textract_response(textract_response)

        if not blocks:
            logger.warning(f"Empty extraction output for {s3_key}")
            return ExtractionResult(
                document_s3_key=s3_key,
                blocks=[],
                total_pages=1,
                status="error",
                error="Empty extraction output"
            )

        # Repair OCR word-fusion (e.g. "firmfoundation") using the PDF's own
        # embedded text layer, which carries the correct spacing. Textract
        # occasionally recognizes two adjacent words as one token; the text
        # layer of a digital-born PDF does not. This is best-effort: any
        # failure leaves the Textract text untouched.
        if is_pdf:
            blocks = _repair_block_spacing(blocks, s3_key, s3_version_id)

        # Sort blocks by reading order
        sorted_blocks = _sort_blocks_by_reading_order(blocks)
        
        # Determine total pages
        total_pages = max(block.page_number for block in sorted_blocks) if sorted_blocks else 1
        
        return ExtractionResult(
            document_s3_key=s3_key,
            blocks=sorted_blocks,
            total_pages=total_pages,
            status="success",
            error=None
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during text extraction for {s3_key}: {e}", exc_info=True)
        return ExtractionResult(
            document_s3_key=s3_key,
            blocks=[],
            total_pages=1,
            status="error",
            error=f"Unexpected error: {str(e)}"
        )


def _extract_sync(textract_client, s3_key: str, s3_version_id: str) -> Dict[str, Any]:
    """
    Perform synchronous Textract extraction.
    
    Args:
        textract_client: Boto3 Textract client
        s3_key: S3 key of the document
        s3_version_id: S3 version ID
        
    Returns:
        Textract response dictionary
    """
    try:
        s3_object = {
            'Bucket': Config.S3_RAW_BUCKET,
            'Name': s3_key
        }
        if s3_version_id:
            s3_object['Version'] = s3_version_id
        
        response = textract_client.analyze_document(
            Document={'S3Object': s3_object},
            FeatureTypes=['TABLES']
        )
        return response
    except ClientError as e:
        logger.error(f"Textract sync extraction failed for {s3_key}: {e}")
        return None


def _extract_async(textract_client, s3_key: str, s3_version_id: str) -> Dict[str, Any]:
    """
    Perform asynchronous Textract extraction.
    
    This uses StartDocumentAnalysis and polls for completion.
    Required for multi-page documents.
    
    Args:
        textract_client: Boto3 Textract client
        s3_key: S3 key of the document
        s3_version_id: S3 version ID
        
    Returns:
        Textract response dictionary with all pages combined
    """
    import time
    
    try:
        s3_object = {
            'Bucket': Config.S3_RAW_BUCKET,
            'Name': s3_key
        }
        if s3_version_id:
            s3_object['Version'] = s3_version_id
        
        # Start async job
        logger.info(f"Starting async Textract job for {s3_key}")
        start_response = textract_client.start_document_analysis(
            DocumentLocation={'S3Object': s3_object},
            FeatureTypes=['TABLES']
        )
        
        job_id = start_response['JobId']
        logger.info(f"Textract job started with ID: {job_id}")
        
        # Poll for completion
        max_attempts = 60  # 5 minutes max (5 second intervals)
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(5)
            attempt += 1
            
            status_response = textract_client.get_document_analysis(JobId=job_id)
            status = status_response['JobStatus']
            
            logger.info(f"Textract job {job_id} status: {status} (attempt {attempt}/{max_attempts})")
            
            if status == 'SUCCEEDED':
                # Collect all pages
                all_blocks = status_response.get('Blocks', [])
                next_token = status_response.get('NextToken')
                
                # Paginate through results if needed
                while next_token:
                    logger.info(f"Fetching next page of results for job {job_id}")
                    next_response = textract_client.get_document_analysis(
                        JobId=job_id,
                        NextToken=next_token
                    )
                    all_blocks.extend(next_response.get('Blocks', []))
                    next_token = next_response.get('NextToken')
                
                logger.info(f"Textract job {job_id} completed successfully with {len(all_blocks)} blocks")
                return {'Blocks': all_blocks}
                
            elif status == 'FAILED':
                logger.error(f"Textract job {job_id} failed")
                return None
                
            elif status in ['IN_PROGRESS', 'PARTIAL_SUCCESS']:
                continue
            else:
                logger.error(f"Unexpected Textract job status: {status}")
                return None
        
        logger.error(f"Textract job {job_id} timed out after {max_attempts} attempts")
        return None
        
    except ClientError as e:
        logger.error(f"Textract async extraction failed for {s3_key}: {e}")
        return None


def _parse_textract_response(response: Dict[str, Any]) -> List[TextBlock]:
    """
    Parse Textract response into TextBlock objects.
    
    Args:
        response: Textract API response
        
    Returns:
        List of TextBlock objects
    """
    blocks = []
    
    for block in response.get('Blocks', []):
        block_type = block.get('BlockType', '')
        
        # We're interested in LINE and CELL blocks
        if block_type not in ['LINE', 'CELL']:
            continue
        
        text = block.get('Text', '')
        if not text:
            continue
        
        page_number = block.get('Page', 1)
        confidence = block.get('Confidence', 0.0) / 100.0  # Convert to 0-1 range
        geometry = block.get('Geometry', {})
        
        # Extract table cell information if present
        row_index = None
        col_index = None
        if block_type == 'CELL':
            row_index = block.get('RowIndex')
            col_index = block.get('ColumnIndex')
            # Textract uses 1-based indexing, convert to 0-based
            if row_index is not None:
                row_index = row_index - 1
            if col_index is not None:
                col_index = col_index - 1
        
        # Map CELL to TABLE_CELL for consistency with design
        mapped_block_type = 'TABLE_CELL' if block_type == 'CELL' else block_type
        
        text_block = TextBlock(
            text=text,
            page_number=page_number,
            block_type=mapped_block_type,
            row_index=row_index,
            col_index=col_index,
            confidence=confidence,
            geometry=geometry
        )
        
        blocks.append(text_block)
    
    return blocks


# Minimum de-spaced length a LINE must have before we attempt a text-layer
# repair. Short lines collide with substrings of longer prose and would match
# ambiguously, so we only repair lines long enough to locate unambiguously.
_MIN_REPAIR_KEY_LEN = 12

# Characters a PDF text layer renders typographically but OCR reports as their
# plain-ASCII equivalent (or vice versa). Matching is done on a folded view so
# these purely-cosmetic differences don't defeat the search. The mapping is
# strictly 1-to-1 (one char in, one char out) so folded offsets stay aligned
# with the unfolded string — this is why NFKC-style normalization, which can
# change length (e.g. "ﬁ" -> "fi", "…" -> "..."), is deliberately not used.
_MATCH_FOLD = str.maketrans(
    {
        **{c: "'" for c in "‘’‚‛′´`"},
        **{c: '"' for c in "“”„‟″"},
        **{c: "-" for c in "‐‑‒–—−"},
    }
)

# Zero-width / invisible characters a PDF text layer may carry that OCR never
# emits. They are dropped from the index entirely (not treated as whitespace),
# so a soft-hyphenated line wrap rejoins into the single word it represents.
_INVISIBLE_CHARS = frozenset("­​‌‍⁠﻿")


def _fold_for_match(text: str) -> str:
    """Fold cosmetic character variants for matching. Length-preserving."""
    return text.translate(_MATCH_FOLD)


def _build_despaced_index(page_text: str) -> tuple[str, List[int]]:
    """
    Build a whitespace-stripped, match-folded view of ``page_text`` plus a map
    from each de-spaced character back to its index in the original text.

    Returns ``(despaced, idx_map)`` where ``despaced[k]`` is the folded form of
    the k-th visible char and ``idx_map[k]`` is its position in ``page_text``.
    Matching on this form lets us locate a Textract line regardless of how its
    spaces were (mis)recognized or how its quotes/dashes were rendered.
    """
    despaced_chars: List[str] = []
    idx_map: List[int] = []
    for pos, ch in enumerate(page_text):
        if ch.isspace() or ch in _INVISIBLE_CHARS:
            continue
        despaced_chars.append(ch)
        idx_map.append(pos)
    return _fold_for_match("".join(despaced_chars)), idx_map


def _repair_line_text(block: TextBlock, page_text: str, despaced: str, idx_map: List[int]) -> str | None:
    """
    Return the spacing-corrected text for a LINE block, or None to leave it.

    Locates the block's de-spaced text in the page's de-spaced text layer; when
    it matches exactly once, re-spaces the block using the word boundaries the
    text layer shows for that span.

    The returned string is built from the BLOCK's own characters — the text
    layer contributes only the positions of the gaps — so ONLY whitespace ever
    changes, never a character. (Rebuilding from the block rather than slicing
    the page is what makes the cosmetic character folding above safe: a folded
    match may pair "don't" with "don’t", and we keep the block's version.)

    Any run of text-layer whitespace between two adjacent characters, including
    a line-wrap newline, becomes exactly one space, matching Textract's
    one-line-per-LINE convention.

    Returns None when the block is ineligible (not a LINE, too short, not
    found, or a non-unique match).
    """
    if block.block_type != "LINE":
        return None

    key = "".join(block.text.split())
    if len(key) < _MIN_REPAIR_KEY_LEN:
        return None

    folded_key = _fold_for_match(key)
    first = despaced.find(folded_key)
    if first == -1:
        return None
    # Require a unique match so we never adopt the wrong occurrence's spacing.
    if despaced.find(folded_key, first + 1) != -1:
        return None

    pieces: List[str] = [key[0]]
    for offset in range(1, len(key)):
        prev_pos = idx_map[first + offset - 1]
        cur_pos = idx_map[first + offset]
        # A gap in the text layer means a word boundary. Invisible characters
        # (soft hyphen, zero-width joiners) alone do not constitute one.
        if any(ch.isspace() for ch in page_text[prev_pos + 1 : cur_pos]):
            pieces.append(" ")
        pieces.append(key[offset])
    return "".join(pieces)


def _repair_block_spacing(
    blocks: List[TextBlock],
    s3_key: str,
    s3_version_id: str,
) -> List[TextBlock]:
    """
    Fix Textract word-fusion in LINE blocks using the PDF's embedded text layer.

    For each LINE block we strip its whitespace and locate that exact character
    sequence in the corresponding page's text layer. When it appears exactly
    once, we adopt the text layer's spacing for that span. The de-spaced forms
    are identical by construction, so ONLY whitespace ever changes — never a
    character. Anything that can't be matched unambiguously is left as-is.

    Best-effort: if PyMuPDF is unavailable, the PDF can't be fetched/opened, or
    a page has no usable text layer (e.g. a scanned page), the original
    Textract blocks are returned unchanged.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Logged at ERROR, not WARNING: this is a deployment defect (the Lambda
        # bundle is missing a declared dependency), not an expected condition.
        # It degrades silently in the output, so it must be loud in the logs.
        logger.error(
            "PyMuPDF not installed; text-layer spacing repair DISABLED — "
            "Textract word-fusion will survive into detection"
        )
        return blocks

    pdf_bytes = _download_pdf_bytes(s3_key, s3_version_id)
    if not pdf_bytes:
        return blocks

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"Could not open PDF text layer for {s3_key}: {e}")
        return blocks

    # Build each page's de-spaced index lazily and once. Cache holds
    # (page_text, despaced, idx_map) or None for pages with no usable text layer.
    page_cache: Dict[int, tuple] = {}

    def _page_data(page_number: int):
        if page_number not in page_cache:
            page_idx = page_number - 1  # Textract Page is 1-based
            data = None
            if 0 <= page_idx < doc.page_count:
                page_text = doc[page_idx].get_text()
                if page_text and not page_text.isspace():
                    despaced, idx_map = _build_despaced_index(page_text)
                    data = (page_text, despaced, idx_map)
            page_cache[page_number] = data
        return page_cache[page_number]

    repaired_count = 0
    repaired_blocks: List[TextBlock] = []
    try:
        for block in blocks:
            page_data = _page_data(block.page_number) if block.block_type == "LINE" else None
            if page_data is not None:
                new_text = _repair_line_text(block, *page_data)
                if new_text is not None and new_text != block.text:
                    block = block.model_copy(update={"text": new_text})
                    repaired_count += 1
            repaired_blocks.append(block)
    finally:
        doc.close()

    if repaired_count:
        logger.info(
            f"Text-layer spacing repair: fixed {repaired_count} block(s) for {s3_key}"
        )
    return repaired_blocks


def _download_pdf_bytes(s3_key: str, s3_version_id: str):
    """Fetch the raw PDF bytes from S3, or None on any failure."""
    try:
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        kwargs = {'Bucket': Config.S3_RAW_BUCKET, 'Key': s3_key}
        if s3_version_id:
            kwargs['VersionId'] = s3_version_id
        response = s3_client.get_object(**kwargs)
        return response['Body'].read()
    except Exception as e:
        logger.warning(f"Could not download PDF bytes for {s3_key}: {e}")
        return None


def _sort_blocks_by_reading_order(blocks: List[TextBlock]) -> List[TextBlock]:
    """
    Sort text blocks by reading order: (page_number, top_position, left_position).
    
    Args:
        blocks: List of TextBlock objects
        
    Returns:
        Sorted list of TextBlock objects
    """
    def get_sort_key(block: TextBlock) -> tuple:
        """Extract sort key from block geometry."""
        geometry = block.geometry
        bounding_box = geometry.get('BoundingBox', {})
        top = bounding_box.get('Top', 0.0)
        left = bounding_box.get('Left', 0.0)
        
        return (block.page_number, top, left)
    
    return sorted(blocks, key=get_sort_key)
