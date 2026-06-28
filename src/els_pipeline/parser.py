"""AI-powered hierarchy parser for ELS pipeline.

Uses Amazon Bedrock (Claude) to resolve parent-child relationships between
DetectedElement objects and produce NormalizedStandard objects. Replaces the
previous rule-based prefix-matching and document-order strategies.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, ReadTimeoutError

from .models import (
    DetectedElement,
    HierarchyLevelEnum,
    NormalizedStandard,
    ParseResult,
    HierarchyLevel,
    StatusEnum,
)
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
MAX_PARSE_RETRIES = 2
MAX_BEDROCK_RETRIES = 2
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 64000
# A single domain chunk asked to resolve too many indicators at once makes the
# LLM silently drop some (observed: AZ "Language and Literacy" with ~22
# indicators in one call lost ~17). Split oversized domain chunks so each LLM
# call stays well within reliable range; cross-chunk strand/sub_strand links are
# re-resolved by the prompt and reconciled by normalize_parsed_codes.
MAX_INDICATORS_PER_CHUNK = 12


def generate_standard_id(
    country: str,
    state: str,
    version_year: int,
    indicator_code: str,
) -> str:
    """
    Generate a deterministic Standard_ID.

    The canonical form is ``{COUNTRY}-{STATE}-{YEAR}-{INDICATOR_CODE}``. The
    indicator_code is expected to already be fully qualified and to carry
    whatever disambiguator is needed so that side-by-side age/column variants
    of the same outcome get distinct IDs — e.g. TX ``PK3.I.A.2`` vs
    ``PK4.I.A.2`` (age prefix), or CA ``ELD.1.0.VOC.1.1.DISC`` vs ``...BRD``
    (column suffix). Keeping the disambiguator inside the indicator_code keeps
    the ID derivation a single clean rule rather than appending age bands here.

    Returns:
        Standard_ID in format: {COUNTRY}-{STATE}-{YEAR}-{INDICATOR_CODE}
    """
    base = f"{country}-{state}-{version_year}-{indicator_code}"
    return base


def canonicalize_age_band(raw: Optional[str]) -> Optional[str]:
    """
    Normalize an age-band string to a bare month range like ``"36-48"``.

    The LLM is asked to convert age bands to months but is inconsistent about
    the surface form — it may emit ``"36-54 months"``, ``"36 - 54"``, or use the
    unicode ``½`` glyph in an un-converted label. This folds all of those to the
    canonical ``"{start}-{end}"`` form the golden uses. Inputs that aren't a
    recognizable numeric month range (None, empty, or a label the LLM failed to
    convert) are returned stripped/unchanged so the caller's fallback and the
    eval's field grading can still surface them.
    """
    if not raw:
        return None
    s = " ".join(str(raw).split())
    m = re.match(
        r"^(\d+)\s*(?:[-–—]|to)\s*(\d+)\s*(?:months?|mos?|mo)?$",
        s,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s or None


def build_parsing_prompt(
    elements: List[DetectedElement],
    country: str,
    state: str,
    version_year: int,
    age_band: str,
) -> str:
    """
    Serialize DetectedElement objects into a structured prompt for the LLM.

    Instructs the LLM to output one JSON object per indicator with full
    hierarchy context including descriptions for each level.

    Args:
        elements: Filtered list of DetectedElement objects (needs_review=False)
        country: Two-letter country code
        state: State abbreviation
        version_year: Version year of the standards document
        age_band: Default age band to use when the LLM cannot detect one

    Returns:
        Prompt string ready to send to Bedrock
    """
    serialized = []
    for el in elements:
        serialized.append({
            "level": el.level.value,
            "code": el.code,
            "title": el.title,
            "description": el.description,
            "age_band": el.age_band,
            "source_page": el.source_page,
            "source_text": el.source_text,
        })

    elements_json = json.dumps(serialized, indent=2)

    prompt = f"""You are an expert at analyzing early learning standards documents. You will be given a list of detected structural elements from a {country}-{state} ({version_year}) standards document. Each element has a level (domain, strand, sub_strand, or indicator), a code, a title, a description, and source information.

Your task is to resolve the hierarchy: assign each indicator to its correct domain, strand, and sub_strand based on the document's structural context and coding scheme.

Here are the detected elements:

{elements_json}

Return a JSON array where each object represents one indicator with its full hierarchy. Use this exact schema for each object:

{{
  "domain_code": "string",
  "domain_name": "string",
  "domain_description": "string or null",
  "strand_code": "string or null",
  "strand_name": "string or null",
  "strand_description": "string or null",
  "sub_strand_code": "string or null",
  "sub_strand_name": "string or null",
  "sub_strand_description": "string or null",
  "indicator_code": "string",
  "indicator_name": "string",
  "indicator_description": "string or null",
  "age_band": "string or null",
  "column_label": "string or null",
  "source_page": integer,
  "source_text": "string"
}}

Rules:
- Populate domain_description, strand_description, and sub_strand_description from the document text (the description field of the corresponding element). Use null if no description exists for that level.
- If a hierarchy level does not exist (e.g. no sub_strand), set its code, name, and description to null.
- For indicator_name: use the actual title of the indicator (e.g. "Curiosity and Interest"), NOT age-band/column labels like "Early", "Later", "Discovering", "PK3", "By 36 months", etc. Strip any such pre-text from the title.
- For indicator_description: use the full descriptive text of the indicator EXACTLY as it appears in the source, INCLUDING any leading proficiency label such as "Discovering:"/"Developing:"/"Broadening:" — that label carries the column's distinguishing content and MUST be kept in the description. (Age-column rows like Early/Later have no such inline label, so nothing is added.) This may be null if no description exists beyond the title.
- For age_band: examine each indicator's code, title, description, source_text, and its detected age_band field for age information. Normalize a real age RANGE to BARE months like "36-48" (PK3 → 36-48, PK4 → 48-60, "3 to 4 ½ Years" → 36-54, "4 to 5 ½ Years" → 48-66). If the column is NOT an age range — e.g. a proficiency level such as "Discovering"/"Developing"/"Broadening" — set age_band to null. The caller applies the default age band "{age_band}" for nulls.
- For column_label: if the indicator came from a side-by-side column, copy that column's label VERBATIM from the element's detected age_band field (e.g. "Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)", "PK3", "Discovering"); otherwise null.
- For code: output the BASE FULL CUMULATIVE hierarchical code for every level — each child's code is its parent's code followed by the child's own segment, NOT just the final segment. A foundation with local code "1.2" under domain "ATL" / strand "1.0" / sub_strand "INIT" → indicator_code "ATL.1.0.INIT.1.2", sub_strand_code "ATL.1.0.INIT", strand_code "ATL.1.0" — never a bare "1.2" or "1.0". When a code is already fully qualified (e.g. an indicator detected as "SED.1.1.a"), use it as-is and derive the parents (strand_code "SED.1", sub_strand_code "SED.1.1").
- When an element's `code` is itself a structural label + identifier (e.g. "Strand 1", "Concept 1", "Goal 2", "Pillar A", "Unit 3" — any structural word the document uses, followed by a number or letter), use ONLY the bare identifier as that element's segment in the cumulative chain: "Strand 1" → segment "1", "Concept 1" → segment "1", "Pillar A" → segment "A". The label word merely names the level and is already captured by the element's `level`; it must NOT appear inside the cumulative `code`. Example: a strand with code "Strand 1" under domain "SED" → strand_code "SED.1" (not "SED.Strand 1"); a sub_strand with code "Concept 1" under that strand → sub_strand_code "SED.1.1" (not "SED.Strand 1.Concept 1"). Apply this to ANY label word, not just the examples.
- PRESERVE the bare identifier VERBATIM — do NOT renumber, pad, or drop any part of it. In particular, keep a decimal/dotted identifier exactly as written, INCLUDING a trailing ".0": "Strand: 1.0" → segment "1.0" (NEVER "1"), "Strand 2.0" → segment "2.0". So a strand labeled "1.0" under domain "ATL" → strand_code "ATL.1.0" (never "ATL.1"). A trailing ".0" is part of the document's id, not a droppable minor version. (This differs from a strand whose id genuinely IS a bare integer — e.g. detected "Strand 1" or derived from an indicator code like "SED.1.1.a" → strand segment "1"; preserve whatever the id actually is.)
- A sub_strand and its child indicator must NEVER share the same code. Some documents number a named sub_strand (e.g. a "Foundation") with the SAME local number that its single child indicator also carries — e.g. a sub_strand titled "Initiative" with local code "1.2" sitting directly above an indicator also coded "1.2". When a sub_strand's local code would otherwise be identical to one of its child indicators' local codes, that shared number belongs to the INDICATOR; derive the sub_strand's OWN segment from its TITLE instead, as a ≤5-char uppercase abbreviation — multi-word titles use the first letter of each word ("Concepts About Print" → "CAP"), single-word titles use the first 4 letters ("Initiative" → "INIT", "Vocabulary" → "VOCA"). Build the cumulative chain with that title-derived segment: sub_strand "Initiative" under domain "ATL" / strand "1.0" → sub_strand_code "ATL.1.0.INIT", and its child indicator (local code "1.2") → indicator_code "ATL.1.0.INIT.1.2". A sub_strand whose code is already distinct from its indicators' (a letter, or an already-abbreviated token like "VOCA") keeps that code unchanged.
- STRIP any leading age/column token from every indicator code: when an indicator appears in multiple side-by-side columns, each variant's detected code may begin with a token identifying its column (e.g. a grade-band prefix like `PK3.` or `PK4.`, an age-group label, or any other column-identifying token prepended to the hierarchical sequence). Strip that leading token and output only the base code shared across all column variants. Then use that stripped indicator code to derive ALL parent codes in the cumulative chain (domain, strand, sub_strand) — the stripped indicator prefix is the ground truth for the parent hierarchy, even if a detected parent element carries a different label. Example: `PK3.I.A.2` and `PK4.I.A.2` → base code `I.A.2`; domain_code=`I`, strand_code=`I.A`.
- SEPARATE domains may legitimately SHARE a strand or sub_strand TITLE, yet they remain DISTINCT entities under DISTINCT domains. For example a document can contain both a "Foundational Language Development" (FLD) domain and an "English Language Development" (ELD) domain, and BOTH may have a "Listening and Speaking" strand AND a "Vocabulary" / "Grammar" / "Phonological Awareness" sub_strand. Every code in an indicator's chain — domain_code, strand_code, AND sub_strand_code — MUST begin with the SAME domain prefix as that indicator's OWN indicator_code. NEVER borrow another domain's prefix for a strand or sub_strand just because the title matches: an indicator coded `FLD.1.0.VOCA.1.1` has strand_code `FLD.1.0` and sub_strand_code `FLD.1.0.VOCA` — NOT `ELD.1.0`/`ELD.1.0.VOCA`, even though the ELD domain has an identically-titled "Vocabulary" sub_strand. Resolve each indicator's parents strictly within its own domain.
- DISAMBIGUATE side-by-side columns by APPENDING a token to the END of the indicator code, so two variants of the same outcome (which share an identical base code) get DISTINCT indicator codes — and therefore distinct standard_ids. Append the token to the INDICATOR code ONLY; NEVER add it to the domain, strand, or sub_strand code. Choose the token by the column's type:
  - AGE-RANGE column (the cell carries an age range — e.g. "Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)", "PK3", "PK4"): append the SAME normalized month range you put in this indicator's `age_band`, written exactly as "{{start}}-{{end}}" (no spaces, no "months"). Examples: a PK3 outcome with base `I.A.2` → `I.A.2.36-48`, its PK4 variant → `I.A.2.48-60`; an "Early" outcome with base `ATL.1.0.INIT.1.2` → `ATL.1.0.INIT.1.2.36-54`, its "Later" variant → `ATL.1.0.INIT.1.2.48-66`. Apply this even when only one age column is present for the outcome (a lone PK4 outcome `VI.A.1` still becomes `VI.A.1.48-60`).
  - NON-AGE column (a proficiency or similar label where the columns share one age range, so `age_band` is null — e.g. "Discovering"/"Developing"/"Broadening"): append the FIRST FOUR LETTERS of the column label, UPPERCASED. Examples: base `ELD.1.0.VOCA.1.1` → `ELD.1.0.VOCA.1.1.DISC` (Discovering), `ELD.1.0.VOCA.1.1.DEVE` (Developing), `ELD.1.0.VOCA.1.1.BROA` (Broadening).
  - If the indicator does NOT come from an age/column cell (no per-column `age_band` and no `column_label`), append NOTHING — leave the base code as-is.
- Return ONLY the JSON array, no other text.
- Every indicator element must appear exactly once in the output.
- There will be cases where you see "No PK3 outcomes for this domain of learning." or similar wording. This means that for the given indicator and age, there is no outcome. In this case, the indicator should be omitted. Do not try to attach it to another indicator.

CRITICAL — RESOLVING HIERARCHY USING CODES AND CONTEXT:
The detected elements come from processing the document in overlapping chunks. This means:
- A strand or sub_strand may have been detected in one chunk while its child indicators were detected in a different chunk. You MUST still link them correctly using code prefixes, naming patterns, and document order.
- Use the hierarchical code structure to resolve parentage. For example, indicators with codes like "PK3.I.A.1" and "PK4.I.A.1" belong under the strand with code "A" (Self-Concept) in domain "I" (Social and Emotional Development).
- If a strand or sub_strand appears in the elements list but has no indicators directly following it, look for indicators elsewhere in the list whose codes or source context indicate they belong under that strand/sub_strand.
- Do NOT drop strands or sub_strands just because their indicators are not adjacent in the element list. Every strand and sub_strand should appear as the parent of at least one indicator in the output (unless it genuinely has no indicators in the document).
- ASSIGN every indicator to the most-recent preceding sub_strand in document order within its strand. A sub_strand header's coverage extends FORWARD across ALL following indicators until the next sub_strand header, the next strand, or the next domain begins. Do this even when those later indicators' local numbers do not look "under" the sub_strand's own number — documents commonly number sub_strands and indicators in ONE flat sequence, so a "Grammar" sub_strand introduced at 1.4 covers foundations 1.4, 1.5, 1.6, 1.7, AND 1.8 right up until "Strand 2.0" begins. NEVER leave an indicator's sub_strand null when a sub_strand precedes it within the same strand; only a strand whose indicators appear before ANY sub_strand header (or a document with no sub_strands at all) yields a null sub_strand."""

    return prompt


def call_bedrock_llm(
    prompt: str,
    max_retries: int = MAX_BEDROCK_RETRIES,
    metrics_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Call Amazon Bedrock LLM with the given prompt.

    Captures and emits token usage and latency metrics.

    Args:
        prompt: The prompt to send to the LLM
        max_retries: Maximum number of retry attempts
        metrics_context: Optional dict with run_id, country, state,
                         batch_index, chunk_index for metric dimensions

    Returns:
        LLM response text

    Raises:
        ClientError: If Bedrock API call fails after all retries
        ValueError: If response format is unexpected
    """
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=Config.AWS_REGION,
        config=BotocoreConfig(
            read_timeout=360,
            connect_timeout=10,
            retries={"max_attempts": 0},
        ),
    )

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": LLM_TEMPERATURE,
    }
    ctx = metrics_context or {}

    logger.info(f"Calling Bedrock with model: {Config.BEDROCK_PARSER_LLM_MODEL_ID}")

    for attempt in range(max_retries + 1):
        try:
            with MetricsTimer() as timer:
                response = bedrock.invoke_model(
                    modelId=Config.BEDROCK_PARSER_LLM_MODEL_ID,
                    body=json.dumps(request_body),
                )
                response_body = json.loads(response["body"].read())

            if "content" not in response_body or len(response_body["content"]) == 0:
                raise ValueError("Unexpected response format from Bedrock: missing content")

            response_text = response_body["content"][0]["text"]
            usage = extract_usage_from_response(response_body)

            # Emit metrics
            call_metrics = LLMCallMetrics(
                stage="parsing",
                model_id=Config.BEDROCK_PARSER_LLM_MODEL_ID,
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

        except (ClientError, ReadTimeoutError) as e:
            if attempt < max_retries:
                logger.warning(
                    f"Bedrock API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                continue
            else:
                # Emit error metrics
                error_metrics = LLMCallMetrics(
                    stage="parsing",
                    model_id=Config.BEDROCK_PARSER_LLM_MODEL_ID,
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

    raise RuntimeError("Failed to get response from Bedrock after all retries")


def _anchor_parent_code(parent_code: str | None, indicator_code: str) -> str | None:
    """Force a parent (domain/strand/sub_strand) code to be a true prefix of its
    indicator's code.

    The parsing prompt treats the indicator code as the ground truth for the
    entire parent chain — every parent code is a leading slice of it. The LLM
    occasionally violates that for domains that SHARE a strand/sub_strand title
    with a sibling domain: e.g. it emits sub_strand ``ELD.1.0.VOCA`` for an
    indicator correctly coded ``FLD.1.0.VOCA.1.1`` because both FLD and ELD have
    a "Vocabulary" sub_strand. We rebuild the parent code from the indicator
    code's leading segments, preserving the parent's own depth, so same-titled
    strands/sub_strands in different domains never collapse onto one domain's
    prefix.

    Segment depth is counted on ``.``-split tokens, which matches the indicator
    code's own structure (a dotted id like ``1.0`` contributes two tokens to
    both the parent and the indicator, so the counts stay aligned). The trailing
    age-band/proficiency disambiguator on the indicator code is excluded
    automatically because parents are always strictly shallower. Idempotent when
    the parent code is already a correct prefix.
    """
    if not parent_code or not indicator_code:
        return parent_code
    ind_segs = indicator_code.split(".")
    depth = len(parent_code.split("."))
    if depth >= len(ind_segs):
        # Parent is not strictly shallower than the indicator — it cannot be a
        # proper prefix; leave it untouched rather than fabricate one.
        return parent_code
    return ".".join(ind_segs[:depth])


def parse_llm_response(
    response_text: str,
    country: str,
    state: str,
    version_year: int,
    fallback_age_band: str,
) -> List[NormalizedStandard]:
    """
    Parse the LLM JSON response into NormalizedStandard objects.

    Strips markdown fences, extracts the JSON array, validates required fields,
    maps descriptions onto HierarchyLevel objects, generates standard IDs, and
    applies the fallback age_band when the LLM returns null.

    Args:
        response_text: Raw text response from the LLM
        country: Two-letter country code
        state: State abbreviation
        version_year: Version year
        fallback_age_band: Age band to use when the LLM returns null

    Returns:
        List of NormalizedStandard objects

    Raises:
        ValueError: If no valid JSON array can be extracted
    """
    text = response_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines[1:] if not line.strip().startswith("```")
        ).strip()

    # Find JSON array boundaries
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        raise ValueError("No valid JSON array found in LLM response")

    data = json.loads(text[start_idx : end_idx + 1])

    required_fields = {"domain_code", "domain_name", "indicator_code", "indicator_name"}
    standards: List[NormalizedStandard] = []
    used_codes: set[str] = set()

    for obj in data:
        if not isinstance(obj, dict):
            logger.warning(f"Skipping non-dict item in LLM response: {obj}")
            continue

        missing = required_fields - obj.keys()
        if missing:
            logger.warning(f"Skipping malformed object, missing fields {missing}: {obj}")
            continue

        try:
            # The indicator code — including any side-by-side column disambiguator
            # token (age-range "36-48" or proficiency "DISC") — now comes straight
            # from the LLM per the parsing prompt. column_label / canonical_age are
            # still read for the age_band field and the proficiency-description prefix.
            column_label = obj.get("column_label")
            canonical_age = canonicalize_age_band(obj.get("age_band"))
            indicator_code = obj["indicator_code"]
            # Thin uniqueness guard: side-by-side variants must keep distinct codes
            # (and standard_ids). The prompt asks the LLM to append the per-column
            # token itself; this only fires if two rows still collide, appending a
            # numeric counter so neither variant is silently dropped downstream.
            if indicator_code in used_codes:
                base = indicator_code
                counter = 2
                while indicator_code in used_codes:
                    indicator_code = f"{base}.{counter}"
                    counter += 1
                logger.warning(
                    "Indicator code collision: '%s' reused; disambiguated to '%s'",
                    base, indicator_code,
                )
            used_codes.add(indicator_code)

            # Build the parents AFTER the indicator code is finalized and anchor
            # every parent code to it. The indicator code is the ground truth for
            # the parent chain, so this keeps same-titled strands/sub_strands in
            # sibling domains (e.g. FLD vs ELD "Vocabulary") from collapsing onto
            # one domain's prefix when the LLM borrows it.
            domain = HierarchyLevel(
                code=_anchor_parent_code(obj["domain_code"], indicator_code),
                name=obj["domain_name"],
                description=obj.get("domain_description"),
            )

            strand = None
            if obj.get("strand_code") and obj.get("strand_name"):
                strand = HierarchyLevel(
                    code=_anchor_parent_code(obj["strand_code"], indicator_code),
                    name=obj["strand_name"],
                    description=obj.get("strand_description"),
                )

            sub_strand = None
            if obj.get("sub_strand_code") and obj.get("sub_strand_name"):
                sub_strand = HierarchyLevel(
                    code=_anchor_parent_code(obj["sub_strand_code"], indicator_code),
                    name=obj["sub_strand_name"],
                    description=obj.get("sub_strand_description"),
                )

            # Proficiency columns (a column label that is NOT an age range, e.g.
            # CA ELD "Discovering"/"Developing"/"Broadening") read in the source as
            # an inline description prefix ("Discovering: <text>"). The detector
            # lifts that label into age_band, so re-prepend it here — it's how the
            # columns' descriptions stay distinguishable and matches the source.
            indicator_description = obj.get("indicator_description")
            if (
                column_label
                and not canonical_age
                and indicator_description
                and not indicator_description.lstrip().lower().startswith(
                    column_label.strip().lower()
                )
            ):
                indicator_description = f"{column_label.strip()}: {indicator_description.strip()}"

            indicator = HierarchyLevel(
                code=indicator_code,
                name=obj["indicator_name"],
                description=indicator_description,
            )

            age_band = canonical_age or fallback_age_band

            standard_id = generate_standard_id(
                country, state, version_year, indicator_code
            )

            source_page = obj.get("source_page", 1)
            source_text = obj.get("source_text", "")

            standards.append(
                NormalizedStandard(
                    standard_id=standard_id,
                    country=country,
                    state=state,
                    version_year=version_year,
                    domain=domain,
                    strand=strand,
                    sub_strand=sub_strand,
                    indicator=indicator,
                    age_band=age_band,
                    source_page=source_page,
                    source_text=source_text,
                )
            )
        except Exception as e:
            logger.warning(f"Skipping object due to validation error: {e} — {obj}")
            continue

    return standards


def normalize_parsed_codes(
    standards: List[NormalizedStandard],
) -> List[NormalizedStandard]:
    """
    Normalize codes across parsed standards so that the same hierarchy entity
    always uses the same code in the final output.

    This handles the case where the parser LLM (called once per domain chunk)
    produces slightly different codes for the same strand/sub_strand name
    across chunks, or where the domain code itself drifts.

    Works at every hierarchy level: domain, strand, sub_strand, indicator.
    For each (level, name) pair, picks the best canonical code using the
    same heuristics as normalize_element_codes.

    Returns:
        New list of NormalizedStandard objects with consistent codes.
    """
    from collections import Counter

    if not standards:
        return standards

    # Collect codes per entity across all standards. The key is scoped by the
    # entity's position in the hierarchy, NOT by its title alone: two different
    # domains can legitimately share a strand title ("Listening and Speaking")
    # and even a sub_strand title ("Vocabulary"). Keying by title only would
    # merge them into one entity and rewrite one domain's codes to the other's.
    # Strands are keyed by (domain, strand_name); sub_strands by
    # (domain, strand_name, sub_strand_name).
    domain_codes: dict[str, Counter] = {}
    strand_codes: dict[tuple[str, str], Counter] = {}
    sub_strand_codes: dict[tuple[str, str, str], Counter] = {}

    for s in standards:
        dk = s.domain.name.strip().lower()
        if dk not in domain_codes:
            domain_codes[dk] = Counter()
        domain_codes[dk][s.domain.code] += 1

        sk = s.strand.name.strip().lower() if s.strand else ""
        if s.strand:
            strand_key = (dk, sk)
            if strand_key not in strand_codes:
                strand_codes[strand_key] = Counter()
            strand_codes[strand_key][s.strand.code] += 1

        if s.sub_strand:
            ss_key = (dk, sk, s.sub_strand.name.strip().lower())
            if ss_key not in sub_strand_codes:
                sub_strand_codes[ss_key] = Counter()
            sub_strand_codes[ss_key][s.sub_strand.code] += 1

    def _pick_canonical(counter: Counter) -> str:
        if len(counter) == 1:
            return next(iter(counter))

        def _sort_key(code_count):
            code, count = code_count
            is_slug = len(code) > 10 or bool(re.search(r'[a-z][A-Z]', code))
            return (is_slug, -count, len(code), code)

        return min(counter.items(), key=_sort_key)[0]

    d_canonical = {name: _pick_canonical(c) for name, c in domain_codes.items()}
    s_canonical = {name: _pick_canonical(c) for name, c in strand_codes.items()}
    ss_canonical = {name: _pick_canonical(c) for name, c in sub_strand_codes.items()}

    # Log normalizations
    for name, counter in domain_codes.items():
        if len(counter) > 1:
            logger.info(
                f"Parsed code normalization: domain '{name}' — "
                f"canonical '{d_canonical[name]}', replaced: "
                f"{[c for c in counter if c != d_canonical[name]]}"
            )
    for key, counter in strand_codes.items():
        if len(counter) > 1:
            logger.info(
                f"Parsed code normalization: strand '{key[0]}/{key[1]}' — "
                f"canonical '{s_canonical[key]}', replaced: "
                f"{[c for c in counter if c != s_canonical[key]]}"
            )
    for key, counter in sub_strand_codes.items():
        if len(counter) > 1:
            logger.info(
                f"Parsed code normalization: sub_strand '{key[0]}/{key[1]}/{key[2]}' — "
                f"canonical '{ss_canonical[key]}', replaced: "
                f"{[c for c in counter if c != ss_canonical[key]]}"
            )

    # Rewrite standards with canonical codes
    result = []
    for s in standards:
        updates = {}

        dk = s.domain.name.strip().lower()
        sk = s.strand.name.strip().lower() if s.strand else ""

        new_domain_code = d_canonical.get(dk, s.domain.code)
        if new_domain_code != s.domain.code:
            updates["domain"] = s.domain.model_copy(update={"code": new_domain_code})

        if s.strand:
            new_strand_code = s_canonical.get((dk, sk), s.strand.code)
            if new_strand_code != s.strand.code:
                updates["strand"] = s.strand.model_copy(update={"code": new_strand_code})

        if s.sub_strand:
            ss_key = (dk, sk, s.sub_strand.name.strip().lower())
            new_ss_code = ss_canonical.get(ss_key, s.sub_strand.code)
            if new_ss_code != s.sub_strand.code:
                updates["sub_strand"] = s.sub_strand.model_copy(update={"code": new_ss_code})

        if updates:
            # Regenerate standard_id if domain code changed
            domain_code = updates.get("domain", s.domain).code
            s = s.model_copy(update=updates)
            new_id = generate_standard_id(
                s.country, s.state, s.version_year,
                s.indicator.code,
            )
            s = s.model_copy(update={"standard_id": new_id})

        result.append(s)

    return result


def normalize_element_codes(
    elements: List[DetectedElement],
) -> List[DetectedElement]:
    """
    Normalize codes across detected elements so that the same entity
    (identified by hierarchy level + name) always uses the same code.

    When the detector processes a document in overlapping chunks, the LLM
    may assign different codes to the same domain/strand/sub_strand across
    chunks (e.g. "PHD" vs "PhysicalDevelopment" for "Physical Development").
    This function picks a single canonical code per (level, name) pair and
    rewrites every element to use it.

    Canonical code selection prefers:
    1. Codes that look like explicit document codes (short, alphanumeric,
       possibly with dots/dashes) over codes that look like slugified names.
    2. Among equally "good" codes, the most frequently occurring one.
    3. Ties broken by shortest length, then lexicographic order.

    Returns:
        New list of DetectedElement objects with normalized codes.
    """
    from collections import Counter

    if not elements:
        return elements

    def _pick(counter: Counter, avoid: frozenset = frozenset()) -> str:
        """Pick the canonical code for one entity: avoid codes that collide with a
        sibling's code (``avoid``), then prefer short alphanumeric document codes
        over long slugified names; then higher frequency, shorter length,
        lexicographic order."""
        if len(counter) == 1:
            return next(iter(counter))

        def _code_sort_key(code_count):
            code, count = code_count
            is_slug = len(code) > 10 or bool(re.search(r'[a-z][A-Z]', code))
            return (code in avoid, is_slug, -count, len(code), code)

        return min(counter.items(), key=_code_sort_key)[0]

    # The same entity can be detected with different codes across overlapping
    # detector chunks (e.g. "PHD" vs "PhysicalDevelopment" for one domain). We
    # pick one canonical code per entity and rewrite every occurrence to it.
    #
    # Scoping matters: two SEPARATE domains can share a strand/sub_strand/
    # indicator TITLE — CA's FLD and ELD domains both have a "Vocabulary"
    # sub_strand and an "Asking Questions" indicator. Keying by title alone would
    # merge them and rewrite one domain's codes onto the other's, e.g.
    # renumbering FLD's "Sharing Explanations" (1.7) to ELD's (1.9). So domain
    # elements reconcile by title, but every NON-domain element is scoped by the
    # (canonical) domain it belongs to.

    # Phase 1 — canonical code per domain title.
    domain_title_codes: dict[str, Counter] = {}
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            t = el.title.strip().lower()
            domain_title_codes.setdefault(t, Counter())[el.code] += 1
    domain_canonical_by_title = {t: _pick(c) for t, c in domain_title_codes.items()}
    raw_domain_to_canonical = {
        el.code: domain_canonical_by_title[el.title.strip().lower()]
        for el in elements
        if el.level == HierarchyLevelEnum.DOMAIN
    }
    raw_domain_codes = list(raw_domain_to_canonical.keys())

    # Assign each element the canonical code of its owning domain: document order,
    # refined by code-prefix inference when the element's own code carries a
    # recognizable domain prefix.
    elem_scope: list[str | None] = []
    current_scope: str | None = None
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            current_scope = raw_domain_to_canonical.get(el.code)
            elem_scope.append(None)  # domains reconcile by title only (phase 1)
        else:
            inferred = _infer_domain_code(el, raw_domain_codes)
            if inferred is not None:
                elem_scope.append(raw_domain_to_canonical.get(inferred, current_scope))
            else:
                elem_scope.append(current_scope)

    # Indicator codes per domain scope — used to keep a reconciled sub_strand
    # code from colliding with a foundation/indicator number in the same strand.
    # A document may detect one sub_strand under two codes: a flat foundation
    # number ("1.4", shared with foundation 1.4) AND a title abbreviation
    # ("GRAM"). Picking the colliding "1.4" makes the LLM emit it literally for
    # the sub_strand's OTHER foundations (1.5–1.8) once they're split into a chunk
    # without foundation 1.4 present — yielding "FLD.1.0.1.4.1.8" instead of
    # "FLD.1.0.GRAM.1.8". Preferring the non-colliding "GRAM" keeps the sub_strand
    # code stable across chunks.
    indicator_codes_by_scope: dict[str | None, set] = {}
    for el, scope in zip(elements, elem_scope):
        if el.level == HierarchyLevelEnum.INDICATOR:
            indicator_codes_by_scope.setdefault(scope, set()).add(el.code)

    # Phase 2 — canonical code per (level, domain scope, title) for non-domains.
    code_groups: dict[tuple, Counter] = {}
    for el, scope in zip(elements, elem_scope):
        if el.level == HierarchyLevelEnum.DOMAIN:
            continue
        key = (el.level.value, scope, el.title.strip().lower())
        code_groups.setdefault(key, Counter())[el.code] += 1
    nondomain_canonical = {}
    for key, counter in code_groups.items():
        level, scope, _ = key
        avoid = (
            frozenset(indicator_codes_by_scope.get(scope, set()))
            if level == HierarchyLevelEnum.SUB_STRAND.value
            else frozenset()
        )
        nondomain_canonical[key] = _pick(counter, avoid)

    # Rewrite every element to its canonical code.
    normalized = []
    for el, scope in zip(elements, elem_scope):
        if el.level == HierarchyLevelEnum.DOMAIN:
            new_code = domain_canonical_by_title.get(el.title.strip().lower(), el.code)
        else:
            key = (el.level.value, scope, el.title.strip().lower())
            new_code = nondomain_canonical.get(key, el.code)
        if new_code != el.code:
            el = el.model_copy(update={"code": new_code})
        normalized.append(el)

    # Log any normalizations that happened.
    for t, counter in domain_title_codes.items():
        if len(counter) > 1:
            winner = domain_canonical_by_title[t]
            logger.info(
                f"Code normalization: domain '{t}' — canonical code '{winner}', "
                f"replaced: {[c for c in counter if c != winner]}"
            )
    for key, counter in code_groups.items():
        if len(counter) > 1:
            level, scope, name = key
            winner = nondomain_canonical[key]
            logger.info(
                f"Code normalization: {level} '{name}' (domain={scope}) — "
                f"canonical code '{winner}', replaced: {[c for c in counter if c != winner]}"
            )

    return normalized


def _infer_domain_code(
    element: DetectedElement,
    domain_codes: List[str],
) -> str | None:
    """
    Infer which domain an element belongs to by matching its code against
    known domain codes.

    Strategy (tried in order):
    1. Prefix match — the element's code starts with a known domain code
       followed by a separator (``.`` or ``-``).  Longer domain codes are
       tried first so that ``III`` is matched before ``I``.
    2. Returns None if no domain can be determined — the caller should
       fall back to document-order assignment.

    This approach is format-agnostic: it works with Roman numerals
    (``I.A.1``), abbreviations (``LLD.A.1``), numeric codes (``1.2.3``),
    and arbitrary strings as long as child codes are prefixed with their
    parent domain code.
    """
    code = element.code

    # Try longest domain codes first so "III" matches before "I"
    for dc in sorted(domain_codes, key=len, reverse=True):
        if code == dc:
            # Exact match (element IS the domain, shouldn't happen for
            # non-domain elements but handle gracefully)
            return dc
        if code.startswith(dc) and len(code) > len(dc):
            # Check that the next character is a separator, not just a
            # longer code that happens to share a prefix
            next_char = code[len(dc)]
            if next_char in ('.', '-', '_'):
                return dc
    return None


def chunk_elements_by_domain(
    elements: List[DetectedElement],
) -> List[List[DetectedElement]]:
    """
    Split elements into chunks grouped by domain for parallel LLM calls.

    Each chunk contains one domain element and all of its descendant strands,
    sub_strands, and indicators.  Non-domain elements are routed to the
    correct domain chunk by matching their code prefix against known domain
    codes, NOT by document order alone.  This is critical because overlapping
    detector chunks can interleave elements from different domains.

    Duplicate domain elements (same code) produced by overlapping detector
    chunks are merged: the one with the richer description is kept.

    Duplicate non-domain elements (same level + code) from overlapping
    detector chunks are deduplicated within each domain group.

    If the input contains no domain-level elements the full list is returned
    as a single chunk so the LLM can still attempt resolution.

    Returns:
        List of element groups, one per unique domain code.
    """
    if not elements:
        return []

    from collections import OrderedDict

    domain_chunks: OrderedDict[str, List[DetectedElement]] = OrderedDict()

    # First pass: collect all domain elements so we know the valid codes
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            code = el.code
            if code not in domain_chunks:
                domain_chunks[code] = [el]
            else:
                # Keep the richer description
                existing_domain = next(
                    (e for e in domain_chunks[code] if e.level == HierarchyLevelEnum.DOMAIN),
                    None,
                )
                if existing_domain and len(el.description or "") > len(
                    existing_domain.description or ""
                ):
                    idx = domain_chunks[code].index(existing_domain)
                    domain_chunks[code][idx] = el

    domain_codes = list(domain_chunks.keys())

    # Second pass: route non-domain elements to the correct domain chunk.
    # We track document-order domain context as a fallback for elements
    # whose codes don't contain a recognisable domain prefix (e.g. bare
    # strand codes like "A", "B").
    current_domain_code: str | None = (
        next(iter(domain_chunks), None) if domain_chunks else None
    )
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            current_domain_code = el.code
            continue

        # Try to infer the correct domain from the element's code
        inferred = _infer_domain_code(el, domain_codes)
        if inferred:
            target = inferred
        elif current_domain_code is not None:
            # Fallback: use the most recently seen domain in document order
            target = current_domain_code
        else:
            # No domain seen yet — park in a placeholder group
            if "__pre__" not in domain_chunks:
                domain_chunks["__pre__"] = []
            domain_chunks["__pre__"].append(el)
            continue

        # Deduplicate overlap-repeated elements (same element re-emitted by
        # adjacent detector chunks). The key includes the normalized title,
        # age_band, AND source_page. source_page distinguishes section-separator
        # strand headers that re-appear on a later page (e.g. AZ "Strand 2:
        # Emergent Literacy" listed as overview on page 4 AND as section header
        # on page 9) from true duplicates produced by overlapping detector chunks
        # (same page, same content). Per-group lettered indicators reuse the same
        # bare code across groups (e.g. AZ 'a' under Concept 2.3 and 'a' under
        # Concept 2.4); column variants share a code with different age bands
        # (CA "1.2" Early vs Later). All five fields together keep intentional
        # repeats distinct while still dropping true same-page duplicates.
        def _dedup_key(e: DetectedElement) -> tuple:
            return (
                e.level,
                e.code,
                " ".join((e.title or "").lower().split()),
                e.age_band,
                e.source_page,
            )

        existing_keys = {
            _dedup_key(e)
            for e in domain_chunks[target]
            if e.level != HierarchyLevelEnum.DOMAIN
        }
        if _dedup_key(el) not in existing_keys:
            domain_chunks[target].append(el)

    chunks = list(domain_chunks.values())

    if not chunks:
        return [elements]

    # Split any domain chunk carrying too many indicators so the LLM isn't asked
    # to resolve more than it reliably can in one call (it otherwise drops some).
    chunks = [sub for chunk in chunks for sub in _split_oversized_chunk(chunk)]

    return chunks


def _split_oversized_chunk(
    chunk: List[DetectedElement],
    max_indicators: int = MAX_INDICATORS_PER_CHUNK,
) -> List[List[DetectedElement]]:
    """Split one domain chunk into sub-chunks of at most ``max_indicators``
    indicators each. Domain element(s) are repeated at the head of every
    sub-chunk so the LLM still knows the domain; the most recently seen strand
    AND sub_strand are also carried forward so sub-chunks that start mid-strand
    still have full parent context for code construction. Splits prefer
    strand/sub_strand boundaries, with a hard cap so a single huge strand still
    gets divided."""
    domain_els = [e for e in chunk if e.level == HierarchyLevelEnum.DOMAIN]
    rest = [e for e in chunk if e.level != HierarchyLevelEnum.DOMAIN]
    n_ind = sum(1 for e in rest if e.level == HierarchyLevelEnum.INDICATOR)
    if n_ind <= max_indicators:
        return [chunk]

    sub_chunks: List[List[DetectedElement]] = []
    cur: List[DetectedElement] = []
    cur_ind = 0
    current_strand: DetectedElement | None = None
    current_sub_strand: DetectedElement | None = None
    for el in rest:
        is_group = el.level in (HierarchyLevelEnum.STRAND, HierarchyLevelEnum.SUB_STRAND)
        if el.level == HierarchyLevelEnum.STRAND:
            current_strand = el
            # A new strand starts a fresh sub_strand scope.
            current_sub_strand = None
        elif el.level == HierarchyLevelEnum.SUB_STRAND:
            current_sub_strand = el
        # Start a new sub-chunk once the current one is full. Prefer to break at a
        # strand/sub_strand boundary, but hard-cap at max_indicators so a long run
        # of indicators under one strand still gets divided.
        if cur and (cur_ind >= max_indicators or (cur_ind >= max_indicators - 2 and is_group)):
            sub_chunks.append(domain_els + cur)
            cur, cur_ind = [], 0
            # Carry the current strand AND sub_strand into the new sub-chunk so the
            # LLM can correctly build hierarchical codes for indicators that appear
            # without an explicit parent header (e.g. AZ Concept 3 under Strand 2,
            # or CA "Phonological Awareness" indicators split off from their PA
            # sub_strand header — otherwise they orphan to sub_strand=None). A new
            # strand/sub_strand header that itself starts the sub-chunk replaces the
            # carried context, so only carry parents shallower than the boundary el.
            if current_strand is not None and el.level != HierarchyLevelEnum.STRAND:
                cur.append(current_strand)
            if (
                current_sub_strand is not None
                and el.level not in (HierarchyLevelEnum.STRAND, HierarchyLevelEnum.SUB_STRAND)
            ):
                cur.append(current_sub_strand)
        cur.append(el)
        if el.level == HierarchyLevelEnum.INDICATOR:
            cur_ind += 1
    if cur:
        sub_chunks.append(domain_els + cur)

    return sub_chunks or [chunk]


def parse_hierarchy(
    elements: List[DetectedElement],
    country: str,
    state: str,
    version_year: int,
    age_band: str,
) -> ParseResult:
    """
    Parse detected elements into normalized standards using an LLM.

    Filters out needs_review elements, splits the remainder into per-domain
    chunks, and calls the LLM once per chunk to stay within Bedrock timeout
    limits.  Results from all chunks are merged into a single ParseResult.

    Args:
        elements: List of DetectedElement objects from the detector
        country: Two-letter country code
        state: State abbreviation
        version_year: Version year of the standards document
        age_band: Default age band (default: "PK")

    Returns:
        ParseResult with standards, indicators, orphaned elements, and status
    """
    try:
        # Filter out elements flagged for review
        valid_elements = [e for e in elements if not e.needs_review]

        if not valid_elements:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=elements,
                status=StatusEnum.ERROR.value,
                error="No valid elements to parse (all flagged for review or empty input)",
            )

        # Normalize codes so the same entity always uses the same code
        # across chunks (e.g. "PHD" and "PhysicalDevelopment" both become "PHD")
        valid_elements = normalize_element_codes(valid_elements)

        # Split into per-domain chunks so each LLM call is small enough
        chunks = chunk_elements_by_domain(valid_elements)
        logger.info(
            f"Split {len(valid_elements)} elements into {len(chunks)} domain chunk(s)"
        )

        all_standards: List[NormalizedStandard] = []
        chunk_errors: List[str] = []

        for chunk_idx, chunk in enumerate(chunks):
            prompt = build_parsing_prompt(
                chunk, country, state, version_year, age_band
            )

            parsed = False
            for parse_attempt in range(MAX_PARSE_RETRIES + 1):
                try:
                    response_text = call_bedrock_llm(prompt)
                    standards = parse_llm_response(
                        response_text, country, state, version_year, age_band
                    )
                    all_standards.extend(standards)
                    parsed = True
                    logger.info(
                        f"Chunk {chunk_idx + 1}/{len(chunks)}: "
                        f"parsed {len(standards)} standards"
                    )
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    if parse_attempt < MAX_PARSE_RETRIES:
                        logger.warning(
                            f"Chunk {chunk_idx + 1} JSON parse failed "
                            f"(attempt {parse_attempt + 1}/{MAX_PARSE_RETRIES + 1}): {e}"
                        )
                        continue
                    else:
                        msg = (
                            f"Chunk {chunk_idx + 1} failed after "
                            f"{MAX_PARSE_RETRIES + 1} attempts: {e}"
                        )
                        logger.error(msg)
                        chunk_errors.append(msg)

        # Determine overall status
        if not all_standards and chunk_errors:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=elements,
                status=StatusEnum.ERROR.value,
                error="; ".join(chunk_errors),
            )

        status = StatusEnum.SUCCESS.value
        error = None
        if chunk_errors:
            status = StatusEnum.PARTIAL.value
            error = "; ".join(chunk_errors)

        # Normalize codes across all parsed standards so the same entity
        # always uses the same code (handles cross-chunk LLM inconsistency)
        all_standards = normalize_parsed_codes(all_standards)

        return ParseResult(
            standards=all_standards,
            indicators=[s.model_dump() for s in all_standards],
            orphaned_elements=[],
            status=status,
            error=error,
        )

    except Exception as e:
        logger.error(f"Unexpected error in parse_hierarchy: {e}")
        return ParseResult(
            standards=[],
            indicators=[],
            orphaned_elements=elements,
            status=StatusEnum.ERROR.value,
            error=f"Parsing failed: {str(e)}",
        )
