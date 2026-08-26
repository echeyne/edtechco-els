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
        elements: List of DetectedElement objects
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
- ABSENCE IS `null`, NEVER `""`. Any description you cannot fill — because the level has no description, or because the corresponding element's own description is null or blank — is `null`. Never write an empty string or a string of spaces for a description field. `""` and `null` are two spellings of the same fact, and emitting both across one document makes the same absence irreconcilable downstream. This applies to every description field in the schema.
- If a hierarchy level does not exist (e.g. no sub_strand), set its code, name, and description to null.
- For indicator_name: use the actual title of the indicator (e.g. "Curiosity and Interest"), NOT age-band/column labels like "Early", "Later", "Discovering", "PK3", "By 36 months", etc. Strip any such pre-text from the title.
- For indicator_description: use the full descriptive text of the indicator EXACTLY as it appears in the source, INCLUDING any leading proficiency label such as "Discovering:"/"Developing:"/"Broadening:" — that label carries the column's distinguishing content and MUST be kept in the description. (Age-column rows like Early/Later have no such inline label, so nothing is added.) This may be null if no description exists beyond the title.
- For age_band: examine each indicator's code, title, description, source_text, and its detected age_band field for age information. Normalize a real age RANGE to BARE months like "36-48" (PK3 → 36-48, PK4 → 48-60, "3 to 4 ½ Years" → 36-54, "4 to 5 ½ Years" → 48-66). If the column is NOT an age range — e.g. a proficiency level such as "Discovering"/"Developing"/"Broadening" — set age_band to null. The caller applies the default age band "{age_band}" for nulls.
- For column_label: if the indicator came from a side-by-side column, copy that column's label VERBATIM from the element's detected age_band field (e.g. "Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)", "PK3", "Discovering"); otherwise null.
- For code: output the BASE FULL CUMULATIVE hierarchical code for every level — each child's code is its parent's code followed by the child's own segment, NOT just the final segment. A foundation with local code "1.2" under domain "AL" / strand "1.0" / sub_strand "INIT" → indicator_code "AL.1.0.INIT.1.2", sub_strand_code "AL.1.0.INIT", strand_code "AL.1.0" — never a bare "1.2" or "1.0". When a code is already fully qualified (e.g. an indicator detected as "SED.1.1.a"), use it as-is and derive the parents (strand_code "SED.1", sub_strand_code "SED.1.1").
- ALREADY-QUALIFIED codes are used AS-IS and are NEVER re-prefixed — at EVERY level, not just the indicator. An element's detected `code` is already qualified when it is a dotted path whose FIRST segment is its own domain's code (after stripping any leading column token, below): an indicator detected as "SED.1.1.a" under domain "SED", or a sub_strand detected as "AB.CD" under domain "AB". For such an element, building the cumulative chain means CONFIRMING that prefix, not prepending it a second time: a sub_strand detected "AB.CD" under domain "AB" and strand "AB.2" → sub_strand_code "AB.CD" — NEVER "AB.2.AB.CD", and NEVER "AB.2.CD". Only an element whose code is a BARE LOCAL segment ("1.2", "A", "INIT", "Concept 1") gets its parents' code prepended.
- A document's printed code NAMESPACE may SKIP a level that its hierarchy HAS. When you derive parent codes by peeling segments off a fully-qualified code, peel only as far as the namespace actually reaches: if peeling one more segment would give a level the SAME code as its own parent, that level is not in the namespace, and you must build it from its OWN heading's identifier appended to its parent's code instead. Worked example — indicators "AB.CD.PK1"/"AB.CD.PK2", a sub_strand detected "AB.CD", a strand whose detected code is "<Something> Standard 2", a domain "AB": peeling gives sub_strand_code "AB.CD" (right), but peeling again would give the strand "AB", which is already the domain's code — so the strand instead takes its heading's bare identifier "2" → strand_code "AB.2". The levels the namespace DOES cover keep the document's spelling exactly: sub_strand_code "AB.CD", indicator_code "AB.CD.PK1". The sub_strand's code then does not literally extend the strand's, and that is the correct answer: the identifier the document PRINTS is the one the standard is cited by, and it outranks cosmetic continuity of the chain.
- When an element's `code` is itself a structural label + identifier (e.g. "Strand 1", "Concept 1", "Goal 2", "Pillar A", "Unit 3" — any structural word the document uses, followed by a number or letter), use ONLY the bare identifier as that element's segment in the cumulative chain: "Strand 1" → segment "1", "Concept 1" → segment "1", "Pillar A" → segment "A". The label word merely names the level and is already captured by the element's `level`; it must NOT appear inside the cumulative `code`. Example: a strand with code "Strand 1" under domain "SED" → strand_code "SED.1" (not "SED.Strand 1"); a sub_strand with code "Concept 1" under that strand → sub_strand_code "SED.1.1" (not "SED.Strand 1.Concept 1"). Apply this to ANY label word, not just the examples.
- PRESERVE the bare identifier VERBATIM — do NOT renumber, pad, or drop any part of it. In particular, keep a decimal/dotted identifier exactly as written, INCLUDING a trailing ".0": "Strand: 1.0" → segment "1.0" (NEVER "1"), "Strand 2.0" → segment "2.0". So a strand labeled "1.0" under domain "AL" → strand_code "AL.1.0" (never "AL.1"). A trailing ".0" is part of the document's id, not a droppable minor version. (This differs from a strand whose id genuinely IS a bare integer — e.g. detected "Strand 1" or derived from an indicator code like "SED.1.1.a" → strand segment "1"; preserve whatever the id actually is.)
- A sub_strand and its child indicator must NEVER share the same code. Some documents number a named sub_strand (e.g. a "Foundation") with the SAME local number that its single child indicator also carries — e.g. a sub_strand titled "Initiative" with local code "1.2" sitting directly above an indicator also coded "1.2". When a sub_strand's local code would otherwise be identical to one of its child indicators' local codes, that shared number belongs to the INDICATOR; derive the sub_strand's OWN segment from its TITLE instead, as a ≤5-char uppercase abbreviation, using the SAME procedure the detector uses: split the title on spaces and slashes (a hyphenated compound is ONE word), DROP every connector word (`a an the and or but nor of to in on at by for from with into about over under through as`, and `&`), then — if exactly one content word remains take its first 4 letters ("Initiative" → "INIT", "Vocabulary" → "VOCA"), otherwise take the first letter of each remaining content word capped at 5 ("Concepts About Print" → "CP", "Approaches to Learning" → "AL"). Build the cumulative chain with that title-derived segment: sub_strand "Initiative" under domain "AL" / strand "1.0" → sub_strand_code "AL.1.0.INIT", and its child indicator (local code "1.2") → indicator_code "AL.1.0.INIT.1.2". A sub_strand whose code is already distinct from its indicators' (a letter, or an already-abbreviated token like "VOCA") keeps that code unchanged. This title-derived segment is a LAST RESORT, exactly as in the detector: it applies only where the document leaves the sub_strand uncoded. A sub_strand that arrives with a printed dotted code ("AB.CD") keeps it and is used as-is per the already-qualified rule above — never replaced by an abbreviation of its title.
- STRIP any leading age/column token from every indicator code: when an indicator appears in multiple side-by-side columns, each variant's detected code may begin with a token identifying its column (e.g. a grade-band prefix like `PK3.` or `PK4.`, an age-group label, or any other column-identifying token prepended to the hierarchical sequence). Strip that leading token and output only the base code shared across all column variants. Then use that stripped indicator code to derive ALL parent codes in the cumulative chain (domain, strand, sub_strand) — the stripped indicator prefix is the ground truth for the parent hierarchy, even if a detected parent element carries a different label. Example: `PK3.I.A.2` and `PK4.I.A.2` → base code `I.A.2`; domain_code=`I`, strand_code=`I.A`.
- SEPARATE domains may legitimately SHARE a strand or sub_strand TITLE, yet they remain DISTINCT entities under DISTINCT domains. For example a document can contain both a "Foundational Language Development" (FLD) domain and an "English Language Development" (ELD) domain, and BOTH may have a "Listening and Speaking" strand AND a "Vocabulary" / "Grammar" / "Phonological Awareness" sub_strand. Every code in an indicator's chain — domain_code, strand_code, AND sub_strand_code — MUST begin with the SAME domain prefix as that indicator's OWN indicator_code. NEVER borrow another domain's prefix for a strand or sub_strand just because the title matches: an indicator coded `FLD.1.0.VOCA.1.1` has strand_code `FLD.1.0` and sub_strand_code `FLD.1.0.VOCA` — NOT `ELD.1.0`/`ELD.1.0.VOCA`, even though the ELD domain has an identically-titled "Vocabulary" sub_strand. Resolve each indicator's parents strictly within its own domain.
- DISAMBIGUATE side-by-side columns by APPENDING a token to the END of the indicator code, so two variants of the same outcome (which share an identical base code) get DISTINCT indicator codes — and therefore distinct standard_ids. Append the token to the INDICATOR code ONLY; NEVER add it to the domain, strand, or sub_strand code. Choose the token by the column's type:
  - AGE-RANGE column (the cell carries an age range — e.g. "Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)", "PK3", "PK4"): append the SAME normalized month range you put in this indicator's `age_band`, written exactly as "{{start}}-{{end}}" (no spaces, no "months"). Examples: a PK3 outcome with base `I.A.2` → `I.A.2.36-48`, its PK4 variant → `I.A.2.48-60`; an "Early" outcome with base `AL.1.0.INIT.1.2` → `AL.1.0.INIT.1.2.36-54`, its "Later" variant → `AL.1.0.INIT.1.2.48-66`. Apply this even when only one age column is present for the outcome (a lone PK4 outcome `VI.A.1` still becomes `VI.A.1.48-60`).
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


# A parent code the parser failed to convert: one label token followed by a
# DOTTED numeric id, e.g. "Benchmark 1.1" or "Foundation 1.7". The id must be
# dotted — a bare "Standard 1" carries no position beyond its own index and is
# not enough evidence to rebuild a qualified code from. Matches on SHAPE only;
# there is deliberately no list of label words, which is what keeps it
# document-agnostic (the same reason `validator._validate_code_shape` keys on
# whitespace rather than on vocabulary).
_LABEL_FORM_CODE_RE = re.compile(r"^(?!\d)(\S+)\s+(\d+(?:\.\d+)+)$")


def _delabel_parent_code(code: str | None, domain_code: str | None) -> str | None:
    """Rebuild a `<Label> <dotted-id>` parent code as `<domain>.<id>`.

    Rule 4 makes a heading's label-and-id the element's code, so the DETECTOR
    correctly emits `Benchmark 1.1` at sub_strand level — the KY detector golden
    annotates exactly that. Converting it to the domain-qualified `LEL.1.1` is
    the PARSER's job, and the parser prompt states it. The model performs it
    most of the time and intermittently does not.

    When it does not, the label form survives into the final record, and because
    `standard_id` is `{country}-{state}-{year}-{indicator_code}`, a whitespace-
    bearing ancestor takes the leaf down with it: the indicator either inherits
    the whitespace or is left bare. Measured on the Task 2 re-record of
    2026-08-26 (`paper/results/task2_20260826/`): 9 of 26 KY rows, all inside a
    single domain — parsing batches by domain, so one call sampled badly while
    the other two were clean. The detection input was byte-identical to the
    previous recording and the parser prompt had not changed, so it is sampling,
    and a primary key needs zero. Same argument as `derive_code_from_title`.

    **A repaired row can only improve.** A code containing whitespace is
    guaranteed to fail `_validate_code_shape` condition 1, so the record was
    going to be rejected before Aurora either way; rebuilding it can recover the
    row and cannot cost one that was already valid.

    Declines when the domain code is itself unusable (absent, or carrying
    whitespace of its own), since prefixing with it would produce a second
    malformed code rather than a repair — the same rule
    `_qualify_bare_indicator_code` follows.
    """
    if not code or not domain_code:
        return code
    if any(c.isspace() for c in domain_code):
        return code
    m = _LABEL_FORM_CODE_RE.match(code)
    if not m:
        return code
    rebuilt = f"{domain_code}.{m.group(2)}"
    logger.info(
        f"LABEL_FORM_PARENT_CODE {code!r} -> {rebuilt!r} "
        f"(domain {domain_code!r}); the parser left rule 4's label form unconverted"
    )
    return rebuilt


def _collapse_duplicated_parent_segment(
    strand_code: str | None,
    sub_strand_code: str | None,
    indicator_code: str,
) -> tuple[str | None, str]:
    """Drop a parent position the child's own printed id already carries.

    A document whose sub-level id is itself DOTTED states its parent's position
    inside that id: Kentucky prints "Benchmark 1.1" under
    "Approaches to Learning Standard 1", where the leading ``1`` IS the
    standard. Composing that id onto the whole strand code counts the standard
    twice — ``AL.1`` + ``1.1`` gives ``AL.1.1.1`` where the document means
    ``AL.1.1``. It is the same principle the parser prompt already states for
    Nevada — peeling stops where the namespace stops — read downward: a child
    that is already qualified relative to its grandparent must not be qualified
    again against its parent.

    The LLM composes this correctly only some of the time, so a prompt rule
    cannot reach zero and `standard_id` needs zero — the argument that put
    `derive_code_from_title` in Python. Measured on the KY full-document run of
    2026-08-25 (`pipeline-US-KY-2021-full08252026`), where the detector input
    was uniform (all 51 sub_strands arrived as ``Benchmark N.N``) and the parser
    still emitted both shapes WITHIN one domain — ``AL.1.1.1`` beside
    ``AL.2.2``, ``CA.1.1`` beside ``CA.1.1.4`` — 78 of 202 rows carried the
    duplicate.

    The tell is purely structural: the sub_strand extends the strand, and the
    first segment it adds repeats the strand's own last segment. That requires
    the added tail to be DOTTED — a single added segment (``AL.2`` → ``AL.2.2``)
    is an ordinary child position and is left alone, which is what keeps the
    rule off documents that simply number their children from 1.

    Scoped to the strand/sub_strand pair, and deliberately not applied to
    domain/strand or to a bare strand+indicator: with no intermediate level to
    compare against there is no way to tell a repeated position from a genuine
    one, and inventing the distinction would corrupt correct codes. Validated
    at ZERO false positives across all 106 annotated standards in all six
    parser goldens.

    Returns the repaired ``(sub_strand_code, indicator_code)`` — the indicator
    is rebuilt too, since it was composed on the duplicated prefix.
    """
    if not strand_code or not sub_strand_code:
        return sub_strand_code, indicator_code

    original_sub, original_indicator = sub_strand_code, indicator_code

    # Iterate to a FIXED POINT rather than collapsing once. A code whose
    # segments repeat ("X.1" / "X.1.1.1") still satisfies the trigger after one
    # collapse, so a single pass leaves a result that would change again if the
    # repair were re-applied — and a repair that is not idempotent cannot be
    # safely re-run on its own output. Real cases are unaffected because they
    # reach the fixed point on the first pass: `AL.1` / `AL.1.1.1` collapses to
    # `AL.1.1`, whose remaining tail is a single segment and stops. Found by
    # `tests/property/test_parser_code_repair_props.py`; shipped non-idempotent
    # at 04e4924c and repaired 2026-08-26.
    while True:
        if not sub_strand_code.startswith(strand_code + "."):
            break
        tail = sub_strand_code[len(strand_code) + 1:]
        if "." not in tail:
            break
        if tail.split(".")[0] != strand_code.split(".")[-1]:
            break
        collapsed = strand_code + "." + tail.split(".", 1)[1]
        if indicator_code.startswith(sub_strand_code + "."):
            indicator_code = collapsed + indicator_code[len(sub_strand_code):]
        sub_strand_code = collapsed

    if sub_strand_code == original_sub:
        return original_sub, original_indicator

    logger.info(
        f"DUPLICATED_PARENT_SEGMENT sub_strand {original_sub!r} -> "
        f"{sub_strand_code!r} (strand {strand_code!r}); indicator "
        f"{original_indicator!r} -> {indicator_code!r}"
    )
    return sub_strand_code, indicator_code


def _collapse_duplicated_indicator_segment(
    strand_code: str | None,
    sub_strand_code: str | None,
    indicator_code: str,
) -> str:
    """Collapse a duplicated parent position the LLM left in the INDICATOR only.

    `_collapse_duplicated_parent_segment` keys on the strand/sub_strand pair, so
    it cannot see a row where the model composed the sub_strand correctly and
    duplicated the segment only in the leaf — KY 2026-08-25 produced exactly one
    (`sub_strand` ``SCIE.1.3`` with `indicator` ``SCIE.1.1.3.DCBO``).

    This repair is SELF-VERIFYING, which is what makes it safe to apply to a
    code no sibling level corroborates: it fires only when the indicator
    currently fails to extend its sub_strand, and only when collapsing makes it
    extend that sub_strand exactly. A change that does not demonstrably repair
    the row's own ancestry is not made. It reads dot structure alone.
    """
    if not strand_code or not sub_strand_code or not indicator_code:
        return indicator_code
    if indicator_code.startswith(sub_strand_code + "."):
        return indicator_code
    if not indicator_code.startswith(strand_code + "."):
        return indicator_code
    tail = indicator_code[len(strand_code) + 1:]
    if "." not in tail or tail.split(".")[0] != strand_code.split(".")[-1]:
        return indicator_code
    collapsed = strand_code + "." + tail.split(".", 1)[1]
    if not collapsed.startswith(sub_strand_code + "."):
        return indicator_code
    logger.info(
        f"DUPLICATED_PARENT_SEGMENT (indicator only) {indicator_code!r} -> "
        f"{collapsed!r} (sub_strand {sub_strand_code!r})"
    )
    return collapsed


def _qualify_bare_indicator_code(
    domain_code: str | None,
    strand_code: str | None,
    sub_strand_code: str | None,
    indicator_code: str,
) -> str:
    """Give a bare indicator code the parent chain the LLM dropped.

    The parser intermittently emits the leaf's own abbreviation with no chain
    at all — a bare ``UMNDW`` where the row's own ancestors say
    ``AL.2.2.UMNDW``. Because `standard_id` is
    ``{country}-{state}-{year}-{indicator_code}``, that is a malformed Aurora
    primary key, and `validator._validate_code_shape` rejects the record before
    it is stored. It is sampling variance rather than a code regression — the
    same defect appears at several code versions and this file already records
    it by name (``TCPHS``, ``UMNDW``) — so the prompt can lower the rate but
    only Python can make the floor zero.

    Measured on the KY full-document run of 2026-08-25: 45 of the 49 rejected
    rows were this, with a correct ancestor chain sitting right beside the bare
    code.

    Fires only on a code carrying NO separator at all, and only when an
    ancestor is present to qualify it with. Every one of the 106 annotated
    standards in the six parser goldens has an indicator code that extends its
    nearest present ancestor, and none is bare — the shallowest is three
    segments — so this only ever moves output toward the goldens. It reads dot
    structure alone, never any document's vocabulary.

    Declines to act when the nearest ancestor is itself malformed: prefixing a
    `<Label> <id>` code that the parser failed to convert would inject
    whitespace into the primary key, replacing one defect with another and
    hiding the real cause from `CODE_SHAPE_GUARD`.
    """
    if not indicator_code or "." in indicator_code:
        return indicator_code
    ancestor = sub_strand_code or strand_code or domain_code
    if not ancestor or ancestor == indicator_code:
        return indicator_code
    if any(c.isspace() for c in ancestor):
        # The nearest ancestor is ITSELF malformed — the parser left a
        # `<Label> <id>` code (e.g. "Benchmark 1.4") unconverted. Prefixing it
        # would inject whitespace into the `standard_id`, i.e. manufacture a
        # SECOND defect on top of the first, and the record would be rejected on
        # the injected whitespace rather than on the real cause. Observed live
        # on `pipeline-US-KY-2021-full08252026-02` (3 rows). A repair must never
        # turn one malformation into a different one, so leave the code alone
        # and let the guard reject it with the diagnosis intact.
        logger.warning(
            f"BARE_INDICATOR_CODE {indicator_code!r} left unqualified: nearest "
            f"ancestor {ancestor!r} is itself malformed (contains whitespace)"
        )
        return indicator_code
    qualified = f"{ancestor}.{indicator_code}"
    logger.info(
        f"BARE_INDICATOR_CODE {indicator_code!r} -> {qualified!r} "
        f"(qualified with nearest ancestor {ancestor!r})"
    )
    return qualified


def _anchor_parent_chain(
    domain_code: str | None,
    strand_code: str | None,
    sub_strand_code: str | None,
    indicator_code: str,
) -> tuple[str | None, str | None, str | None]:
    """Anchor a whole parent chain to the indicator's code, stopping where the
    document's printed namespace stops.

    ``_anchor_parent_code`` assumes the indicator code spells out every
    ancestor, which is true only when the document codes every level. Some
    documents print a namespace that SKIPS a level: Nevada codes its indicators
    ``<domain>.<sub_strand>.PKn`` and gives the strand its own heading
    identifier ("Social Studies Standard 2") that appears nowhere in the
    indicator code. Anchoring each level independently then peels the SAME
    prefix for two different levels — NV's strand and sub_strand both become
    ``SS.CI`` — which silently discards the strand's real identity and makes
    two distinct strands share one code.

    The tell is purely structural and needs no knowledge of any document: if a
    level's anchored code EQUALS the anchored code of the level directly below
    it, the peel has run past the end of the namespace. That level is outside
    it and keeps the identifier its own heading supplied.

    Applied top-down from the deepest parent so each comparison is made against
    an already-resolved child. Idempotent, and a no-op for documents whose
    indicator codes do spell out every ancestor (AZ/CA/CO/KY/TX), where no two
    levels ever peel to the same prefix.

    A level held OUTSIDE the namespace keeps its heading identifier, and that
    identifier is the LLM's, not the document's — so its leading segment can
    carry a stale domain code. Nevada shows both spellings of the same leak
    across two runs of one document: strand ``TECH.1`` under domain ``T``, and
    strand ``Science.1`` under domain ``S``, where the detector's title-derived
    domain code leaked into a strand code the anchor could not rebuild. A
    strand's code always extends its own domain's code — measured at 106/106
    over every annotated standard in all six golden states, and 508/508 over
    two full six-state pipeline runs once NV's 11 leaked rows are excluded. So
    when the strand's leading segment disagrees with the resolved domain, the
    domain wins and the segment is replaced.

    Two guards keep that from cutting the wrong way, and both are load-bearing:

    * It fires only when the DOMAIN was successfully anchored. If the domain is
      the level that fell outside the namespace, its code is the unreliable one
      — re-rooting an anchored strand onto it would corrupt a correct code.
    * It REPLACES a leading segment, never prepends one, so it only acts on a
      strand code that already has a domain-code slot to correct. A
      single-segment strand identifier is left alone: there is nothing to
      replace, and prepending would invent a qualification the document never
      printed.
    """
    anchored_sub = _anchor_parent_code(sub_strand_code, indicator_code)
    anchored_strand = _anchor_parent_code(strand_code, indicator_code)
    anchored_domain = _anchor_parent_code(domain_code, indicator_code)

    strand_outside = bool(
        anchored_strand and anchored_sub and anchored_strand == anchored_sub
    )
    if strand_outside:
        anchored_strand = strand_code
    domain_outside = bool(
        anchored_domain and anchored_strand and anchored_domain == anchored_strand
    )
    if domain_outside:
        anchored_domain = domain_code

    if (
        strand_outside
        and not domain_outside
        and anchored_domain
        and anchored_strand
        and "." in anchored_strand
        and anchored_strand != anchored_domain
        and not anchored_strand.startswith(anchored_domain + ".")
    ):
        anchored_strand = ".".join(
            [anchored_domain] + anchored_strand.split(".")[1:]
        )

    return anchored_domain, anchored_strand, anchored_sub


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
            # The indicator code — including any side-by-side column disambiguator
            # token (age-range "36-48" or proficiency "DISC") — now comes straight
            # from the LLM per the parsing prompt. column_label / canonical_age are
            # still read for the age_band field and the proficiency-description prefix.
            column_label = obj.get("column_label")
            canonical_age = canonicalize_age_band(obj.get("age_band"))
            indicator_code = obj["indicator_code"]
            # Uniqueness is NOT resolved here. This function runs once per
            # chunk, so it cannot see a collision that spans two of them, and
            # renaming the second row to arrive would make the surviving code
            # depend on chunk order — the wrong property for a primary key.
            # `disambiguate_colliding_standards` handles it after the merge.

            # Repair the codes the LLM composed BEFORE anchoring. The indicator
            # code is the ground truth for the whole chain, so a duplicated
            # segment left in it here is faithfully propagated into every
            # parent. Order matters: collapsing the duplicate can itself make an
            # otherwise non-extending indicator extend its ancestor again (a
            # sub_strand `MATH.1.1.2` repaired to `MATH.1.2` is exactly the
            # ancestor `MATH.1.2.RNSBS` was built on), so it runs first.
            # De-label first: the later repairs all reason about dot structure,
            # and a `<Label> <id>` code has none they can read.
            strand_code = _delabel_parent_code(
                obj.get("strand_code"), obj["domain_code"]
            )
            sub_strand_code, indicator_code = _collapse_duplicated_parent_segment(
                strand_code,
                _delabel_parent_code(obj.get("sub_strand_code"), obj["domain_code"]),
                indicator_code,
            )
            indicator_code = _collapse_duplicated_indicator_segment(
                strand_code, sub_strand_code, indicator_code
            )
            indicator_code = _qualify_bare_indicator_code(
                obj["domain_code"],
                strand_code,
                sub_strand_code,
                indicator_code,
            )

            # Build the parents AFTER the indicator code is finalized and anchor
            # every parent code to it. The indicator code is the ground truth for
            # the parent chain, so this keeps same-titled strands/sub_strands in
            # sibling domains (e.g. FLD vs ELD "Vocabulary") from collapsing onto
            # one domain's prefix when the LLM borrows it.
            anchored_domain, anchored_strand, anchored_sub = _anchor_parent_chain(
                obj["domain_code"],
                strand_code,
                sub_strand_code,
                indicator_code,
            )

            domain = HierarchyLevel(
                code=anchored_domain,
                name=obj["domain_name"],
                description=obj.get("domain_description"),
            )

            strand = None
            if obj.get("strand_code") and obj.get("strand_name"):
                strand = HierarchyLevel(
                    code=anchored_strand,
                    name=obj["strand_name"],
                    description=obj.get("strand_description"),
                )

            sub_strand = None
            if obj.get("sub_strand_code") and obj.get("sub_strand_name"):
                sub_strand = HierarchyLevel(
                    code=anchored_sub,
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

            # Localization for `validator._validate_code_shape`. That guard is
            # the pipeline's chokepoint for a malformed primary key, but it sees
            # only the FINAL record — so a CODE_SHAPE_GUARD rejection reports the
            # chain, the page and the standard_id while saying nothing about what
            # the model actually emitted. The two historical defect shapes are
            # distinguishable only from the pre-normalization codes: a structural
            # label left in ("ELD.2.0.PA.Foundation 2.3.DISC") versus a parent
            # chain dropped entirely (bare "TCPHS"). Emitting the raw codes keyed
            # by standard_id lets a rejection be grepped straight back to the
            # LLM's own output. Logged for every row, not just changed ones,
            # because whether a row will be rejected is not knowable here.
            logger.info(
                f"PRE_NORMALIZATION_CODES {standard_id}: "
                f"llm_emitted={{'domain': {obj['domain_code']!r}, "
                f"'strand': {obj.get('strand_code')!r}, "
                f"'sub_strand': {obj.get('sub_strand_code')!r}, "
                f"'indicator': {obj['indicator_code']!r}}} "
                f"anchored={{'domain': {anchored_domain!r}, "
                f"'strand': {anchored_strand!r}, "
                f"'sub_strand': {anchored_sub!r}}}"
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


def _collision_tiebreak_key(standard: NormalizedStandard) -> tuple:
    """Order colliding rows by where they sit in the DOCUMENT, not by when they
    happened to be parsed.

    The numeric fallback below hands one row the bare code and the next a `.2`
    suffix, and those become Aurora primary keys. Enumerating the group in
    arrival order made that assignment depend on chunk/batch scheduling, so the
    same document could write different keys on different runs — the exact
    property `disambiguate_colliding_standards` exists to remove, reintroduced
    in its own last resort.

    Every component is read off the document: the page the standard was found
    on, the source line, then the indicator's name and description to separate
    two rows printed on one page. Rows identical on all four are
    indistinguishable in the output anyway, so their relative order cannot
    matter.
    """
    return (
        standard.source_page or 0,
        standard.source_text or "",
        standard.indicator.name or "",
        standard.indicator.description or "",
    )


def disambiguate_colliding_standards(
    standards: List[NormalizedStandard],
    country: str,
    state: str,
    version_year: int,
) -> List[NormalizedStandard]:
    """Give every standard a unique indicator code, and hence a unique
    ``standard_id``.

    A document's printed code namespace is not always unique. Nevada prints
    ``SS.CI.PK3`` for two different standards — "Recognize and resolve
    conflicts with peers WITH ADULT GUIDANCE" under Social Studies Standard 5
    and "...IN AN AGE-APPROPRIATE MANNER" under Standard 2 — because its codes
    skip the strand, and the strand is the only thing separating them. Left
    alone that is a duplicate Aurora primary key for two distinct standards.

    Resolution is by ANCESTOR first: when the colliding rows sit under
    different parents whose codes extend their shared domain code, each row's
    code is re-qualified with its own parent's segments (``SS.2.CI.PK3`` and
    ``SS.5.CI.PK3``). Every member of the colliding set is rewritten, including
    the first one seen, so the result does not depend on which row was parsed
    first — the same document always yields the same ids.

    A numeric counter is the fallback for rows a parent cannot separate
    (identical parents, or parents that share a code). That case IS
    order-dependent, so it is a last resort and is logged as one.

    Rows that do not collide are returned untouched.
    """
    from collections import defaultdict

    if not standards:
        return standards

    by_code: dict[str, List[NormalizedStandard]] = defaultdict(list)
    for s in standards:
        by_code[s.indicator.code].append(s)

    taken = {code for code, group in by_code.items() if len(group) == 1}

    for code, group in by_code.items():
        if len(group) < 2:
            continue

        # Ancestor pass: re-qualify each row with its own parent's code. The
        # parent must extend the domain code for the splice to be meaningful,
        # and the indicator code must start from that same domain.
        proposals: List[str | None] = []
        for s in group:
            parent = s.strand.code if s.strand else None
            dom = s.domain.code
            if (
                parent
                and dom
                and parent != dom
                and parent.startswith(f"{dom}.")
                and s.indicator.code.startswith(f"{dom}.")
            ):
                proposals.append(parent + s.indicator.code[len(dom):])
            else:
                proposals.append(None)

        usable = (
            all(p is not None for p in proposals)
            and len(set(proposals)) == len(proposals)
            and not (set(proposals) & taken)
        )

        if usable:
            logger.warning(
                "Indicator code '%s' shared by %d standards; disambiguated by "
                "ancestor to %s",
                code, len(group), sorted(p for p in proposals if p),
            )
            for s, new_code in zip(group, proposals):
                s.indicator.code = new_code  # type: ignore[assignment]
                s.standard_id = generate_standard_id(
                    country, state, version_year, new_code  # type: ignore[arg-type]
                )
                taken.add(new_code)  # type: ignore[arg-type]
            continue

        # Fallback: numeric counter, assigned in DOCUMENT order so the result
        # is reproducible. Nothing in the hierarchy separates these rows, so the
        # suffix carries no meaning — but it must at least be the same suffix
        # every run, since it lands in a primary key. See
        # `_collision_tiebreak_key`.
        logger.warning(
            "Indicator code '%s' shared by %d standards and their parents do "
            "not separate them; falling back to a positional numeric suffix "
            "assigned in document order (page, source line, name). The ids are "
            "reproducible, but the suffix encodes nothing about the standard.",
            code, len(group),
        )
        for idx, s in enumerate(sorted(group, key=_collision_tiebreak_key)):
            new_code = code if idx == 0 else f"{code}.{idx + 1}"
            while new_code in taken:
                idx += 1
                new_code = f"{code}.{idx + 1}"
            s.indicator.code = new_code
            s.standard_id = generate_standard_id(
                country, state, version_year, new_code
            )
            taken.add(new_code)

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


def _pick_code(counter, avoid: frozenset = frozenset()) -> str:
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


def canonical_domain_codes(
    elements: List[DetectedElement],
) -> tuple[dict, dict]:
    """
    Reconcile the codes of domain-level elements by domain TITLE.

    Domains are the one level that can safely reconcile on title alone — a
    document does not repeat a domain name for two different domains, but it
    may emit the same domain under different codes in different chunks
    (e.g. "SED" in one chunk, "I" in the next).

    Returns:
        (canonical_by_title, raw_code_to_canonical)
    """
    from collections import Counter

    domain_title_codes: dict[str, Counter] = {}
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            t = el.title.strip().lower()
            domain_title_codes.setdefault(t, Counter())[el.code] += 1
    canonical_by_title = {t: _pick_code(c) for t, c in domain_title_codes.items()}
    raw_to_canonical = {
        el.code: canonical_by_title[el.title.strip().lower()]
        for el in elements
        if el.level == HierarchyLevelEnum.DOMAIN
    }
    return canonical_by_title, raw_to_canonical


def assign_domain_scopes(elements: List[DetectedElement]) -> List[Optional[str]]:
    """
    Assign every element the canonical code of the domain it belongs to.

    Scope is resolved by document order (the most recent domain heading seen),
    refined by code-prefix inference when the element's own code carries a
    recognizable domain prefix (``LLD.1.2`` under domain ``LLD``). Domain
    elements themselves get scope ``None`` — they reconcile by title.

    This is the shared notion of "which parent does this element sit under"
    used both by :func:`normalize_element_codes` (so two domains that share a
    strand title are not merged) and by the detector's overlap de-duplication
    (so two same-titled elements under DIFFERENT domains are not collapsed).
    """
    _, raw_to_canonical = canonical_domain_codes(elements)
    raw_domain_codes = list(raw_to_canonical.keys())

    scopes: List[Optional[str]] = []
    current_scope: Optional[str] = None
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            current_scope = raw_to_canonical.get(el.code)
            scopes.append(None)
        else:
            inferred = _infer_domain_code(el, raw_domain_codes)
            if inferred is not None:
                scopes.append(raw_to_canonical.get(inferred, current_scope))
            else:
                scopes.append(current_scope)
    return scopes


def code_domain_scopes(elements: List[DetectedElement]) -> List[Optional[str]]:
    """
    Assign every element the domain implied by its OWN code, or None.

    Identical to :func:`assign_domain_scopes` minus the document-order
    fallback — and that omission is the whole point.

    Use this to answer IDENTITY questions ("are these two rows the same
    occurrence of one element?"). Document order is a property of the element
    LIST, and chunk overlap is exactly what perturbs that list: a re-emitted
    element can land past a later domain heading and inherit that domain even
    though it is the same occurrence as its twin a few positions earlier. Keying
    identity on an order-derived scope is therefore circular — it is most wrong
    precisely for the duplicates it is meant to tell apart. A code-derived scope
    is a property of the element itself, so both twins always agree on it.

    Use :func:`assign_domain_scopes` for CONTEXT questions ("which domain does
    this element sit under?"), where the order fallback is what you want.

    Returns None for domain elements (they reconcile by title) and for any
    element whose code carries no recognizable domain prefix.
    """
    _, raw_to_canonical = canonical_domain_codes(elements)
    raw_domain_codes = list(raw_to_canonical.keys())

    scopes: List[Optional[str]] = []
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            scopes.append(None)
            continue
        inferred = _infer_domain_code(el, raw_domain_codes)
        scopes.append(raw_to_canonical.get(inferred) if inferred is not None else None)
    return scopes


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
    domain_canonical_by_title, _ = canonical_domain_codes(elements)

    # Assign each element the canonical code of its owning domain: document order,
    # refined by code-prefix inference when the element's own code carries a
    # recognizable domain prefix.
    elem_scope = assign_domain_scopes(elements)

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
        nondomain_canonical[key] = _pick_code(counter, avoid)

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

    Splits the elements into per-domain chunks and calls the LLM once per
    chunk to stay within Bedrock timeout limits.  Results from all chunks
    are merged into a single ParseResult.

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
        valid_elements = elements

        if not valid_elements:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=elements,
                status=StatusEnum.ERROR.value,
                error="No valid elements to parse (empty input)",
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

        # Then resolve any remaining duplicate indicator codes. This runs after
        # the merge (a collision can span two chunks) and after normalization
        # (which can itself bring two rows onto one code).
        all_standards = disambiguate_colliding_standards(
            all_standards, country, state, version_year
        )

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
