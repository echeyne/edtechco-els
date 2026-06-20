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


# Number of leading letters used to abbreviate a proficiency-style column label
# (Discovering → DISC, Developing → DEVE, Broadening → BROA). Age-distinguished
# columns use their month range instead, so this only fires for non-age labels.
_COLUMN_ABBREV_LEN = 4
# Leading age/column token to drop from a fully-qualified code, e.g. the "PK3."
# in "PK3.I.A.2" — the disambiguator is re-applied as a suffix instead.
_COLUMN_PREFIX_RE = re.compile(r"^PK\d+\.", re.IGNORECASE)


def _strip_column_prefix(code: Optional[str]) -> Optional[str]:
    """Drop a leading age/column token (e.g. ``PK3.``/``PK4.``) from a code so the
    base hierarchical path is shared across side-by-side variants. No-op for codes
    without such a prefix."""
    if not code:
        return code
    return _COLUMN_PREFIX_RE.sub("", code)


def _derive_label_abbrev(label: Optional[str]) -> Optional[str]:
    """Derive a stable disambiguator from a proficiency-style column label: the
    first ``_COLUMN_ABBREV_LEN`` alphabetic characters, uppercased
    (``Discovering`` → ``DISC``, ``Developing`` → ``DEVE``, ``Broadening`` →
    ``BROA``). Returns None if the label has no usable letters."""
    if not label:
        return None
    letters = re.sub(r"[^A-Za-z]", "", label)
    return letters[:_COLUMN_ABBREV_LEN].upper() or None


def _disambiguator_suffix(
    canonical_age: Optional[str],
    column_label: Optional[str],
) -> Optional[str]:
    """The suffix appended to an indicator code so side-by-side column variants
    keep distinct codes/IDs. Age-distinguished columns (Early/Later, PK3/PK4) use
    the canonical month range (e.g. ``36-48``); proficiency columns that share one
    age band (Discovering/Developing/Broadening) use a derived label abbreviation."""
    if canonical_age:
        return canonical_age
    if column_label:
        return _derive_label_abbrev(column_label)
    return None


# A structural-label code ("Strand 1", "Concept B", "Section 3") — the trailing
# identifier IS the real code segment, so "Strand 1" → "1". Mirrors the
# detector's _LABEL_PREFIX_RE but captures the identifier instead of stripping it.
_LABEL_CODE_RE = re.compile(
    r"^\s*(?:strand|concept|sub-?strand|section|standard|domain|goal|benchmark|unit|part)"
    r"\s+([A-Za-z0-9][\w.\-]*)\s*$",
    re.IGNORECASE,
)
# Length of a deterministic abbreviation for a single-word title (Vocabulary →
# VOCA). Multi-word titles use an acronym of every word instead.
_CODE_ABBREV_LEN = 4


def _abbreviate_title(title: str) -> str:
    """Deterministic short code from a title: acronym of every word for
    multi-word titles ("Concepts About Print" → "CAP", "Social Emotional
    Development" → "SED"), else the first _CODE_ABBREV_LEN letters of a
    single word ("Vocabulary" → "VOCA"). Uppercased."""
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    if not words:
        return ""
    if len(words) >= 2:
        return "".join(w[0] for w in words).upper()
    return words[0][:_CODE_ABBREV_LEN].upper()


def normalize_code_to_canonical(code: Optional[str], title: Optional[str]) -> Optional[str]:
    """Map a detected element's code to a clean, deterministic code SEGMENT for
    cumulative-code building:

    1. ``"Strand 1"`` / ``"Concept 2"`` (structural label + identifier) → the
       identifier (``"1"`` / ``"2"``).
    2. A code that is itself a title/phrase — it contains a space, or equals the
       element's title — → a deterministic abbreviation of the title
       (``"Concepts About Print"`` → ``"CAP"``, ``"Vocabulary"`` → ``"VOCA"``).
    3. Otherwise the code already looks like a real short code (``"SED"``,
       ``"1.0"``, ``"VOC"``, ``"a"``) → keep it unchanged.
    """
    if not code:
        return code
    c = code.strip()
    m = _LABEL_CODE_RE.match(c)
    if m:
        return m.group(1)
    t = (title or "").strip()
    if (" " in c) or (t and c.lower() == t.lower()):
        return _abbreviate_title(t or c) or c
    return c


_PURE_NUMERIC_RE = re.compile(r"^\d[\d.]*$")


def abbreviate_element_codes(
    elements: List[DetectedElement],
) -> List[DetectedElement]:
    """Rewrite each element's code to its canonical short form (see
    normalize_code_to_canonical) so the LLM builds cumulative codes from clean,
    consistent segments (e.g. AZ "Strand 1"/"Concept 1" → "1"/"1", giving
    "SED.1.1.a" instead of "SED.Strand 1.Concept 1.a"). Runs after
    normalize_element_codes in both the direct and batched parse paths."""
    # Pre-compute normalised indicator codes so we can detect the CA pattern
    # where a sub_strand element inherits the same Foundation number as its
    # child indicators (e.g. sub_strand code="1.2" title="Initiative" sits above
    # indicator code="1.2" title="Initiative [Early]"). In that case the numeric
    # code belongs to the indicator; the sub_strand's identity is its title.
    indicator_codes: set[str] = set()
    for el in elements:
        if el.level == HierarchyLevelEnum.INDICATOR:
            nc = normalize_code_to_canonical(el.code, el.title)
            if nc:
                indicator_codes.add(nc)

    out: List[DetectedElement] = []
    for el in elements:
        new_code = normalize_code_to_canonical(el.code, el.title)
        if (
            el.level == HierarchyLevelEnum.SUB_STRAND
            and new_code
            and _PURE_NUMERIC_RE.match(new_code)
            and new_code in indicator_codes
            and el.title
        ):
            title_abbrev = _abbreviate_title(el.title)
            if title_abbrev:
                logger.info(
                    "Code normalization: sub_strand '%s' (numeric code '%s' "
                    "collides with indicator) → title abbreviation '%s'",
                    el.title,
                    new_code,
                    title_abbrev,
                )
                new_code = title_abbrev
        if new_code and new_code != el.code:
            el = el.model_copy(update={"code": new_code})
        out.append(el)
    return out


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
- STRIP any leading age/column token from every code: a detected indicator code like "PK3.I.A.2" or "PK4.I.A.2" must become the BASE code "I.A.2" (drop the "PK3."/"PK4." prefix). Do NOT append the age band or column label to any code yourself — the caller appends a disambiguator suffix so side-by-side variants stay distinct.
- Return ONLY the JSON array, no other text.
- Every indicator element must appear exactly once in the output.
- There will be cases where you see "No PK3 outcomes for this domain of learning." or similar wording. This means that for the given indicator and age, there is no outcome. In this case, the indicator should be omitted. Do not try to attach it to another indicator.

CRITICAL — RESOLVING HIERARCHY USING CODES AND CONTEXT:
The detected elements come from processing the document in overlapping chunks. This means:
- A strand or sub_strand may have been detected in one chunk while its child indicators were detected in a different chunk. You MUST still link them correctly using code prefixes, naming patterns, and document order.
- Use the hierarchical code structure to resolve parentage. For example, indicators with codes like "PK3.I.A.1" and "PK4.I.A.1" belong under the strand with code "A" (Self-Concept) in domain "I" (Social and Emotional Development).
- If a strand or sub_strand appears in the elements list but has no indicators directly following it, look for indicators elsewhere in the list whose codes or source context indicate they belong under that strand/sub_strand.
- Do NOT drop strands or sub_strands just because their indicators are not adjacent in the element list. Every strand and sub_strand should appear as the parent of at least one indicator in the output (unless it genuinely has no indicators in the document)."""

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

    for obj in data:
        if not isinstance(obj, dict):
            logger.warning(f"Skipping non-dict item in LLM response: {obj}")
            continue

        missing = required_fields - obj.keys()
        if missing:
            logger.warning(f"Skipping malformed object, missing fields {missing}: {obj}")
            continue

        try:
            # Drop any leading age/column token (PK3./PK4.) so the base path is
            # shared across side-by-side variants; the disambiguator is re-applied
            # as a suffix on the indicator code below.
            domain = HierarchyLevel(
                code=_strip_column_prefix(obj["domain_code"]),
                name=obj["domain_name"],
                description=obj.get("domain_description"),
            )

            strand = None
            if obj.get("strand_code") and obj.get("strand_name"):
                strand = HierarchyLevel(
                    code=_strip_column_prefix(obj["strand_code"]),
                    name=obj["strand_name"],
                    description=obj.get("strand_description"),
                )

            sub_strand = None
            if obj.get("sub_strand_code") and obj.get("sub_strand_name"):
                sub_strand = HierarchyLevel(
                    code=_strip_column_prefix(obj["sub_strand_code"]),
                    name=obj["sub_strand_name"],
                    description=obj.get("sub_strand_description"),
                )

            # Resolve the indicator code: base cumulative path (PK prefix stripped)
            # + a disambiguator suffix for side-by-side column variants so Early vs
            # Later (age) and Discovering vs Developing (proficiency) stay distinct.
            column_label = obj.get("column_label")
            canonical_age = canonicalize_age_band(obj.get("age_band"))
            suffix = _disambiguator_suffix(canonical_age, column_label)
            indicator_code = _strip_column_prefix(obj["indicator_code"])
            if suffix and not indicator_code.endswith(suffix):
                indicator_code = f"{indicator_code}.{suffix}"

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

    # Collect codes per (level, name) across all standards
    domain_codes: dict[str, Counter] = {}
    strand_codes: dict[str, Counter] = {}
    sub_strand_codes: dict[str, Counter] = {}

    for s in standards:
        dk = s.domain.name.strip().lower()
        if dk not in domain_codes:
            domain_codes[dk] = Counter()
        domain_codes[dk][s.domain.code] += 1

        if s.strand:
            sk = s.strand.name.strip().lower()
            if sk not in strand_codes:
                strand_codes[sk] = Counter()
            strand_codes[sk][s.strand.code] += 1

        if s.sub_strand:
            ssk = s.sub_strand.name.strip().lower()
            if ssk not in sub_strand_codes:
                sub_strand_codes[ssk] = Counter()
            sub_strand_codes[ssk][s.sub_strand.code] += 1

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
    for name, counter in strand_codes.items():
        if len(counter) > 1:
            logger.info(
                f"Parsed code normalization: strand '{name}' — "
                f"canonical '{s_canonical[name]}', replaced: "
                f"{[c for c in counter if c != s_canonical[name]]}"
            )
    for name, counter in sub_strand_codes.items():
        if len(counter) > 1:
            logger.info(
                f"Parsed code normalization: sub_strand '{name}' — "
                f"canonical '{ss_canonical[name]}', replaced: "
                f"{[c for c in counter if c != ss_canonical[name]]}"
            )

    # Rewrite standards with canonical codes
    result = []
    for s in standards:
        updates = {}

        new_domain_code = d_canonical.get(s.domain.name.strip().lower(), s.domain.code)
        if new_domain_code != s.domain.code:
            updates["domain"] = s.domain.model_copy(update={"code": new_domain_code})

        if s.strand:
            new_strand_code = s_canonical.get(s.strand.name.strip().lower(), s.strand.code)
            if new_strand_code != s.strand.code:
                updates["strand"] = s.strand.model_copy(update={"code": new_strand_code})

        if s.sub_strand:
            new_ss_code = ss_canonical.get(s.sub_strand.name.strip().lower(), s.sub_strand.code)
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

    # Group codes by (level, normalized_name)
    code_groups: dict[tuple[str, str], Counter] = {}
    for el in elements:
        key = (el.level.value, el.title.strip().lower())
        if key not in code_groups:
            code_groups[key] = Counter()
        code_groups[key][el.code] += 1

    # For each group, pick the canonical code
    canonical: dict[tuple[str, str], str] = {}
    for key, counter in code_groups.items():
        if len(counter) == 1:
            canonical[key] = next(iter(counter))
            continue

        # Score each code: prefer short, alphanumeric codes (real document
        # codes) over long slugified names.
        def _code_sort_key(code_count):
            code, count = code_count
            # A "document code" is short and uses only alphanumerics, dots,
            # dashes, underscores.  A "slugified name" is longer and often
            # contains no separators or uses camelCase / full words.
            is_slug = len(code) > 10 or bool(re.search(r'[a-z][A-Z]', code))
            return (
                is_slug,      # False (real code) sorts before True (slug)
                -count,       # Higher frequency first
                len(code),    # Shorter first
                code,         # Lexicographic tiebreak
            )

        best = min(counter.items(), key=_code_sort_key)
        canonical[key] = best[0]

    # Build a mapping from old code to new code per (level, name)
    # and rewrite elements
    normalized = []
    for el in elements:
        key = (el.level.value, el.title.strip().lower())
        new_code = canonical.get(key, el.code)
        if new_code != el.code:
            el = el.model_copy(update={"code": new_code})
        normalized.append(el)

    # Log any normalizations that happened
    for key, counter in code_groups.items():
        if len(counter) > 1:
            level, name = key
            winner = canonical[key]
            others = [c for c in counter if c != winner]
            logger.info(
                f"Code normalization: {level} '{name}' — "
                f"canonical code '{winner}', replaced: {others}"
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
    1. Prefix match — the element's code (after stripping common age-band
       prefixes like ``PK3.``, ``PK4.``) starts with a known domain code
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
    # Strip common age-band prefixes (e.g. PK3., PK4.)
    stripped = re.sub(r'^PK\d+\.', '', code)

    # Try longest domain codes first so "III" matches before "I"
    for dc in sorted(domain_codes, key=len, reverse=True):
        if stripped == dc:
            # Exact match (element IS the domain, shouldn't happen for
            # non-domain elements but handle gracefully)
            return dc
        if stripped.startswith(dc) and len(stripped) > len(dc):
            # Check that the next character is a separator, not just a
            # longer code that happens to share a prefix
            next_char = stripped[len(dc)]
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
    element is also carried forward so sub-chunks that start mid-strand still
    have parent context for code construction. Splits prefer strand/sub_strand
    boundaries, with a hard cap so a single huge strand still gets divided."""
    domain_els = [e for e in chunk if e.level == HierarchyLevelEnum.DOMAIN]
    rest = [e for e in chunk if e.level != HierarchyLevelEnum.DOMAIN]
    n_ind = sum(1 for e in rest if e.level == HierarchyLevelEnum.INDICATOR)
    if n_ind <= max_indicators:
        return [chunk]

    sub_chunks: List[List[DetectedElement]] = []
    cur: List[DetectedElement] = []
    cur_ind = 0
    current_strand: DetectedElement | None = None
    for el in rest:
        is_group = el.level in (HierarchyLevelEnum.STRAND, HierarchyLevelEnum.SUB_STRAND)
        if el.level == HierarchyLevelEnum.STRAND:
            current_strand = el
        # Start a new sub-chunk once the current one is full. Prefer to break at a
        # strand/sub_strand boundary, but hard-cap at max_indicators so a long run
        # of indicators under one strand still gets divided.
        if cur and (cur_ind >= max_indicators or (cur_ind >= max_indicators - 2 and is_group)):
            sub_chunks.append(domain_els + cur)
            cur, cur_ind = [], 0
            # Carry the current strand into the new sub-chunk so the LLM can
            # correctly build hierarchical codes for sub_strands/indicators that
            # appear without an explicit strand header (e.g. AZ Concept 3 under
            # Strand 2 split across a chunk boundary).
            if current_strand is not None and el.level != HierarchyLevelEnum.STRAND:
                cur.append(current_strand)
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
        # Canonicalize code segments ("Strand 1"→"1", "Concepts About Print"→"CAP")
        # so cumulative codes come out clean and deterministic.
        valid_elements = abbreviate_element_codes(valid_elements)

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
