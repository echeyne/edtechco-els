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
# Cross-chunk code reconciliation and domain scoping are shared with the parser
# — the detector's overlap de-duplication reuses them rather than re-deriving
# "which entity is this, and whose child is it".
from .parser import assign_domain_scopes, code_domain_scopes, normalize_element_codes
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

# Grounding check: everything except letters and digits is dropped before
# comparing a title to its own source_text, so the comparison survives the
# differences that legitimately arise between the two — line breaks inside a
# wrapped heading, OCR punctuation and quote-glyph drift, and the ALL-CAPS
# running-header normalization prompt rule 4 asks for ("SOCIAL EMOTIONAL
# DEVELOPMENT STANDARD" → "Social Emotional Development").
_GROUNDING_STRIP_RE = re.compile(r"[^a-z0-9]+")

# A `<Label>: <id>` code keeps the colon the HEADING used to separate the two
# ("Strand: 1.0" from "Strand: 1.0 — Listening and Speaking"), and the LLM
# applies it inconsistently — CA emits "Strand: 1.0" six times and "Strand 2.0"
# once, so one construct ends up with two spellings and the same strand fails
# to reconcile across chunks. The canonical form is label, one space, id; the
# separator is layout.
#
# Document-agnostic by construction: it keys on the SHAPE (a leading alphabetic
# label, a colon, a remainder), never on which word the label is, so it holds
# for Strand/Concept/Goal/Pillar or whatever a given document uses. Scoped to
# the colon deliberately — a hyphen or dot inside a code is usually meaningful
# ("1.0-V", "PK3.I.A.2", "A-1"), whereas a colon in a code is essentially
# always the heading's label separator leaking through.
_CODE_LABEL_SEPARATOR_RE = re.compile(r"^([A-Za-z][A-Za-z-]*)\s*:\s*(\S.*)$")

# Prompt rule 4's abbreviation procedure, expressed for `derive_code_from_title`.
# Keep these in lockstep with rule 4 in `build_detection_prompt` and with the
# parser prompt's restatement of the same procedure — three copies of one rule,
# and they must agree.
_CODE_CONNECTORS = frozenset(
    "a an the and or but nor of to in on at by for from with into about over "
    "under through as".split()
) | {"&"}
# (a) split on whitespace and slashes only — a hyphenated compound is ONE word
# ("self-selected" contributes a single "S"), while "Health/Mental Wellness" is
# three words.
_CODE_WORD_SPLIT_RE = re.compile(r"[\s/]+")
# Rule 4(b) matches connectors "ignoring trailing punctuation", so strip the
# non-alphanumerics bracketing a word before testing and before taking its
# initial.
_CODE_WORD_STRIP_RE = re.compile(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$")
DERIVED_CODE_MAX_LEN = 5
DERIVED_CODE_SINGLE_WORD_LEN = 4

# Shortest run of shared characters that may anchor a cross-chunk prose splice
# (`_splice_overlapping_prose`). Long enough that a shared sentence opener or a
# boilerplate clause repeated across domains cannot pass for a real overlap,
# short enough to survive a chunk boundary landing mid-sentence.
_MIN_PROSE_OVERLAP = 60

# The same `<Label>: <id>` → `<Label> <id>` fold `_CODE_LABEL_SEPARATOR_RE`
# performs, but unanchored so it can be applied inside a source_text line as
# well as to a code. Used by `_is_code_grounded` to compare a canonicalized
# code against the page's original spelling.
_CODE_LABEL_COLON_RE = re.compile(r"(?<=[A-Za-z])\s*:\s*")

# The only shape rule 4's abbreviation branch can produce: uppercase letters,
# at most `DERIVED_CODE_MAX_LEN` of them. A code outside this shape came from
# the document — a number ("1.0"), a dotted path ("PK3.I.A.2"), a labelled id
# ("Benchmark 1.1"), or a list letter ("a") — and is never recomputed.
_DERIVABLE_CODE_RE = re.compile(rf"^[A-Z]{{1,{DERIVED_CODE_MAX_LEN}}}$")

DEFAULT_OVERLAP_TOKENS = 500

# Overlap de-duplication: a title must be longer than this (normalized chars)
# before it may be treated as the truncated prefix of a longer title. Short
# label-like titles ("Vocabulary", "Grammar") are legitimately shared or
# extended by sibling elements, so prefix dominance must not reach them.
MIN_PREFIX_TITLE_CHARS = 12

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


# --------------------------------------------------------------------------
# Layout geometry (EXPERIMENTAL — self-contained; remove `_block_left`, drop
# the x= term from `_serialize_blocks_for_prompt`, and delete the LAYOUT
# COORDINATES prompt paragraph to revert to plain "[Page N] text".)
#
# Textract gives every block a normalized BoundingBox, but the prompt used to
# discard it. On a multi-column page (side-by-side age bands or proficiency
# levels) the blocks arrive interleaved line-by-line, so a serialization that
# keeps only the page number leaves the LLM no way to tell which column a line
# came from — and it crosses the columns' contents.
#
# We pass the raw left edge through and let the MODEL group lines into
# columns. Clustering the edges here in Python would mean deciding the
# document's layout on the model's behalf — and a mis-clustered line reaches
# the model as wrong evidence it has no way to recover from. Emitting the
# coordinate keeps this function to "read a float off the block and print it"
# and leaves the judgment where the rest of the detector's judgment lives.
# --------------------------------------------------------------------------


def _block_left(block: TextBlock) -> Optional[float]:
    """Return a block's normalized left edge (0.0–1.0), or None if unusable."""
    geometry = block.geometry if isinstance(block.geometry, dict) else None
    bbox = geometry.get("BoundingBox") if geometry else None
    if not isinstance(bbox, dict):
        return None
    try:
        left = float(bbox["Left"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0.0 <= left <= 1.0:
        return None
    return left


def _serialize_blocks_for_prompt(blocks: List[TextBlock]) -> str:
    """
    Render text blocks as prompt lines, tagging each with its page and its
    normalized left edge on that page:
    ``[Page 12 | x=0.09] Attend to and participate``.

    Blocks whose geometry is missing or degenerate fall back to ``[Page N]``,
    so a scanned page with no usable BoundingBox still serializes cleanly.

    Blocks stay in DOCUMENT order rather than being re-sorted by coordinate.
    Re-sorting would break two things the rest of the pipeline depends on:
    ``chunk_text_blocks`` slices this same block sequence into overlapping
    chunks, so a reordered stream would put a column's tail in a different
    chunk from its head; and row adjacency is what ties the columns of one
    age-band row together. The tag carries the layout signal without moving
    anything.
    """
    lines = []
    for block in blocks:
        left = _block_left(block)
        tag = (
            f"[Page {block.page_number} | x={left:.2f}]"
            if left is not None
            else f"[Page {block.page_number}]"
        )
        lines.append(f"{tag} {block.text}")
    return "\n".join(lines)


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
    text_content = _serialize_blocks_for_prompt(blocks)

    return f"""You are analyzing the structural skeleton of an early learning standards document. You will NOT extract individual elements — only the document's nesting hierarchy.

Read the sample below and identify how many distinct nesting depths the document uses, what each depth looks like (its prefix/label pattern), and one concrete example. The DEEPEST depth is always the leaf (individual learning goals/foundations/benchmarks).

This document's depths must then be mapped to a canonical 4-level hierarchy:
- depth 1 → "domain"
- depth 2 → "strand"
- depth 3 → "sub_strand"
- deepest depth → "indicator"

Rules:
- Fill the canonical levels FROM THE TOP DOWN. The first depth is always "domain", the deepest depth is always "indicator", and any depth in between takes the next canonical level in order: the depth directly under domain is "strand", the one below that is "sub_strand". A document with fewer depths therefore drops the levels at the BOTTOM of that middle range — never "strand".
- A 4-level document (domain > group > sub-group > leaf) maps to: domain, strand, sub_strand, indicator.
- A 3-level document (domain > group > leaf) maps to: domain, strand, indicator. There is NO sub_strand — the single middle level is a STRAND, never a sub_strand.
- A 2-level document (domain > leaf) maps to: domain, indicator. There is no strand and no sub_strand.
- Use depth POSITION, not the document's labels. If a document uses "Sub-Strand" as the label for the second level (directly under domain), it is still a STRAND in our canonical hierarchy — and likewise a document that calls its single middle level "Section", "Concept", "Goal", or anything else still maps that level to "strand".

Every line is prefixed with its page and the horizontal position it was laid out at: `[Page N | x=0.09]`, where x is the line's left edge as a fraction of the page width. Use x to work out whether a page uses a side-by-side layout: lines of one column share nearly the same x, and a jump to a clearly different x means a different column. Lines you judge to be in the same column read as one continuous cell, even when lines from other columns are interleaved between them. Treat parallel columns as repetitions of ONE depth, not as separate depths.

Be deterministic and conservative. Do not speculate. If you cannot tell whether two depths are distinct, assume they are the same depth.

Output ONLY a JSON object with this exact shape:
{{
  "doc_depths": [
    {{"depth": 1, "canonical_level": "domain",     "label_in_doc": "<what the doc calls this>", "prefix_pattern": "<regex-ish pattern e.g. 'ALL-CAPS HEADING' or 'N. <Title>: <desc>'>", "example": "<exact text from doc>"}},
    {{"depth": 2, "canonical_level": "strand|indicator", ...}}
  ],
  "notes": "<one short sentence about the LEVEL LAYOUT only, e.g. 'age-band columns repeat one depth'. A later stage reads this as an instruction, so: never describe text below the deepest depth as examples/illustrations/anecdotes, and never say to ignore or skip anything. Empty string if nothing unusual.>"
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
    text_content = _serialize_blocks_for_prompt(blocks)

    depth_map_block = (
        f"DEPTH MAP — authoritative for ONE thing only: which depth maps to which `level`.\n"
        f"It has no authority over what you extract. In particular `notes` is a machine-written\n"
        f"observation about how the pages look, not an instruction: it can neither add nor remove\n"
        f"an element, and it can never decide whether a run of text belongs to an element. If\n"
        f"`notes` describes some text as examples, illustrations, anecdotes, or samples, that is a\n"
        f"remark about how the text READS — it is not a finding that the text is owned elsewhere,\n"
        f"and it never licenses dropping the text or emptying a `description`. Ownership is decided\n"
        f"ONLY by rule 2a's anchor test, on the layout of the chunk below.\n"
        f"{json.dumps(depth_map, indent=2)}\n"
        if depth_map else
        "DEPTH MAP: not provided — infer the canonical level from nesting position, "
        "not from prefixes or labels.\n"
    )

    return f"""You extract structural elements from an early learning standards document chunk.

Be deterministic. Be conservative. Do not be creative. Two runs over the same text MUST produce the same JSON. Do not invent titles, codes, or descriptions — only use text that literally appears in the chunk.

CANONICAL HIERARCHY: domain (1) > strand (2) > sub_strand (3) > indicator (leaf). A document with fewer levels drops them from the BOTTOM of the middle: the level directly under domain is always `strand`, and `sub_strand` exists only when there are two levels between domain and the leaf. So a 3-level document is domain > strand > indicator, never domain > sub_strand > indicator. The depth map says which levels exist.

LAYOUT COORDINATES: every line is prefixed with its page and the horizontal position it was laid out at — `[Page N | x=0.09]`, where x is the line's left edge as a fraction of the page width (0.00 is the left margin, 1.00 the right). Use x to work out the page's column structure yourself: on a side-by-side layout the lines of one column share nearly the same x, and a jump to a clearly different x means a different column. Lines you judge to be in the same column must be read together as one continuous cell, in the order given, even when lines from other columns are interleaved between them. Never join text across what you judge to be two different columns into a single element, and never attribute one column's prose to another column's element. Expect a header that spans the whole layout to sit at the leftmost x while belonging to every column beneath it. A line tagged only `[Page N]` has no usable coordinate; use the text's own layout cues there.

CLASSIFICATION RULE:
- If a depth map is provided, look up each element's depth in the document and use the `canonical_level` from that depth. Do NOT reclassify based on prefix style.
- If no depth map is provided, classify by nesting POSITION, never by what the document calls a level.

EXTRACTION RULES:
1. Emit every structural element you see, even if its children are not in this chunk. Emit ONLY what you see: every element must be backed by a heading line that literally appears in this chunk, and its `title` must be text copied from that line. A position identifier you read inside a CHILD's code is NOT evidence that the parent's heading is present. A child code names its ancestors — an indicator coded `A.B.2.c` says it sits under the `2` at the level above — but that tells you only where the child belongs; it does not put the parent's heading on the page. When a chunk opens part-way through a section and an ancestor's heading was left behind in the previous chunk, emit the children alone and leave the ancestor out. A later chunk that contains the heading will supply it, and the parent is reconstructed downstream from the children's codes. Never reconstruct it here by reading the code apart. Emit ONLY what you see: every element must be backed by a heading line that literally appears in this chunk. (This says only that the heading must BE there — how you split that line into `title`, `code`, and `description` is decided by rules 4 and 8 as usual, and this rule never tells you to copy the whole line into `title`.) A position identifier you read inside a CHILD's code is NOT evidence that the parent's heading is present. A child code names its ancestors — an indicator coded `A.B.2.c` says it sits under the `2` at the level above — but that tells you only where the child belongs; it does not put the parent's heading on the page. When a chunk opens part-way through a section and an ancestor's heading was left behind in the previous chunk, emit the children alone and leave the ancestor out. A later chunk that contains the heading will supply it, and the parent is reconstructed downstream from the children's codes. Never reconstruct it here by reading the code apart.
2. A lettered/bulleted list (a., b., c., …) is EITHER the leaf indicators OR illustrative examples below a leaf — decide using the depth map, never the "a./b." surface style:
   - If the document's DEEPEST depth in the depth map is this lettered list (i.e. there is no deeper indicator level beneath the letters), then EACH lettered item IS an indicator. Emit one indicator per letter. Its `title` is the lettered item's own skill/competency statement (the text after the letter, e.g. "a. Demonstrates self-confidence." → "Demonstrates self-confidence"); any further example anecdotes indented beneath that letter go in its `description`. Do NOT fold these letters away and do NOT drop them — every lettered item in the chunk must appear.
   - Otherwise (the letters sit BELOW an already-identified leaf indicator and read as concrete behavior anecdotes, not skill statements) they are an EXAMPLE LIST — see rule 2a. Do NOT emit them as separate indicators.
2a. EXAMPLE LISTS — decide by OWNERSHIP, not by how illustrative the text sounds. This applies only to text the depth map does NOT place at a structural depth; anything at a depth is an element (rule 2) and is emitted regardless of how example-like it reads. For the remaining, non-structural text, find the run's owner with this exact two-step test, in this order:
   STEP 1 — Find the ANCHOR. Scan UPWARD from the run's first line and stop at the very first line that the depth map places at a structural depth. That element is the ANCHOR. Its depth is irrelevant: the anchor is the NEAREST element above the run, never the section's top-level heading. A leaf indicator is an anchor exactly like a domain or strand is — including a lettered item that rule 2 made an indicator.
   STEP 2 — Look ONLY at the lines lying strictly BETWEEN the anchor and the run. Nothing above the anchor is part of this test.
   - A heading or lead-in line lies in that gap — a non-structural line that names the run as a category rather than asserting a requirement ("Child Behaviors", "Examples", "The child may:", "For example:"). That line owns the run, and it is a section label rather than a structural element, so NOTHING from the run is extracted: do not emit the lead-in, do not emit the entries, and do NOT copy the entries into the anchor. The anchor's `description` keeps only its own prose, which is often absent — write `null` then. The same holds for a run laid out full-width BENEATH side-by-side columns: it is owned by no single column, so it enters no column's `description`.
   - The gap is empty — the run simply continues directly underneath the anchor. Then it IS the anchor's own text, however anecdotal or example-like it reads. Put it in the anchor's `description`, verbatim. Never discard text merely because it illustrates: discard it only when the document has given it somewhere else to belong. Being CALLED an example is not being given somewhere else to belong — not by the depth map's `notes`, not by a section header higher up the page, not by your own reading of the tone. Only a lead-in sitting in the gap does that.
   A heading's claim is SPENT the moment a structural element appears beneath it. A section header followed by structural elements is a label for that GROUP and hands ownership DOWN to them; it never reaches past them to claim text nested under one of them. This holds even when the header's own wording announces examples — a header that names both the indicators and their examples still owns nothing itself, and each indicator beneath it owns the example lines nested under that indicator.
   Either way, such a run is never promoted to elements of its own.
3. Side-by-side age-band columns: emit ONE element PER column. Different age bands = different indicators, even when they share a code stem and title. Set `age_band` to the column label (e.g. "Early (3 to 4 ½ Years)", "PK3", "By 36 months"). Strip the age-band label from `title`. Put only that column's prose in `description`. If a row shows N age columns it MUST yield exactly N indicators — emit EVERY column even when a column's prose is short, nearly identical to its neighbor, or visually sparse. Never collapse or skip a column.
   - Spell each age-band label identically every time, using the document's exact glyphs (write "½", not "1/2").
4. `code`: use the document's code if present. Before you decide none is present, LOOK for it — a document often prints an element's code somewhere other than on its heading line, and a code you can RECOVER from the page ALWAYS beats one you would derive from the title. Search these three places, in this order, and stop at the first that yields a code:
   (i) ON THE HEADING LINE — a code printed inline with the title ("1.0", "I.A.2", "PK3.I.A.2"), including the `<Label> <id>` form described in the bullets below. This always wins: an element that prints its own id keeps it, even when its descendants' codes are built on a different stem.
   (ii) IN A CAPTION BESIDE THE HEADING — a code the document prints just above, below, or beside the title rather than on it: inside parentheses, on a small caption line, in a table or column header, or in a lead-in that names the group of items which follows. A heading "Working Memory" whose next line reads "Indicators (CD.WM)" has code "CD.WM". Take only the IDENTIFIER — the caption's surrounding words ("Indicators", "Standards", "Codes") name what the caption points at and are not part of the code — and copy it VERBATIM, dots included.
   (iii) FROM ITS DESCENDANTS' CODES — the heading prints no code of its own anywhere, but the elements BENEATH it carry dotted codes that all begin with the same segments. An ancestor's code is the COMMON PREFIX of its descendants' document codes. Indicators coded "CD.WM.PK1", "CD.WM.PK2", "CD.AT.PK1", "CD.AT.PK2" say that the group heading above the first two is "CD.WM", the group above the last two is "CD.AT", and the level above all four is "CD". Emit the WHOLE shared prefix with its dots ("CD.WM") — never just its last segment ("WM"), and never an abbreviation of the title.
       Peel exactly ONE segment per level as you move UP, so a recovered prefix never reaches past the level directly below it: the parent of an indicator coded "CD.WM.PK1" is "CD.WM", and the level above THAT is "CD". A level that prints its own code under (i) takes that code and consumes NO segment — keep peeling from where you were for the level above it. Peel this way even when the chunk happens to show only one group under a heading, where the raw shared prefix would over-reach ("CD.WM" for a level that is really "CD").
       Take a prefix only when the evidence is real:
       - The descendant's code must have MORE THAN ONE dot-separated segment. A single-segment code ("1", "a", "VOCA") names only the element itself and holds no ancestor inside it.
       - At least TWO descendants must agree on the prefix AND differ after it. One descendant alone cannot show where its code stops naming ancestors and starts naming itself.
       - Only WHOLE segments count. Never split a segment.
       - A descendant code that carries a structural LABEL word ("Foundation 1.7", "Benchmark 1.1", "Standard 2") is NOT a namespace path: the label names that descendant's OWN level, so the entire id after the label belongs to the descendant and none of it is an ancestor's code. Take a prefix only from bare dotted codes ("CD.WM.PK1", "I.A.2").
       This rule decides WHICH code an element gets. It NEVER licenses emitting an element you cannot see — rule 1 still governs that, and the heading line must literally appear in this chunk. If it does not, emit the descendants alone and take nothing from them.
   When (ii) or (iii) supplied the code, cite the line it came from in `source_text` IN ADDITION to the heading line — that line is part of the text you used (rule 7). Never instead of the heading line: rule 1's self-check still holds, and if a descendant's line is the ONLY line you can cite, you did not see the heading and must not emit the element at all.
   ONLY when all three come up empty — the document leaves this element genuinely uncoded — do you generate a stable ≤5-char uppercase abbreviation from the title, by this EXACT procedure:
   (a) Split the title into words on spaces and slashes. A hyphenated compound is ONE word ("self-selected" → one word contributing "S"; "Health/Mental Wellness" → three words).
   (b) DROP every CONNECTOR word. A connector is any of: `a an the and or but nor of to in on at by for from with into about over under through as`, and the symbol `&`. Connectors carry no meaning in a code — their initials only crowd out the words that do, and the code has just 5 characters to spend. Keeping them yields a code made of function words: "Attends to an adult or peer who is communicating verbally or nonverbally" would give "ATAAO" ("Attends To An Adult Or") instead of "AAPWI", and "Engages in an activity for a sustained period of time" would give "EIAAF" instead of "EASPT". The code is the human-readable part of a standard's identifier, so it must spend its characters on the words that name the skill. This list is exact — do not extend it to other prepositions you may consider connector-like ("toward", "during", "between", "despite", "while"): those are CONTENT words for this purpose and their initials stay in the code. Match case-insensitively and ignore trailing punctuation.
   (c) If exactly ONE content word remains, the code is its first 4 letters ("Vocabulary" → "VOCA", "Initiative" → "INIT"). Otherwise the code is the first letter of each remaining content word, in order, capped at the first 5 ("Physical Development" → "PD", "Approaches to Learning" → "AL", "Concepts About Print" → "CP", "Social & Emotional Development" → "SED", "Language and Early Literacy" → "LEL", "Engages in an activity for a sustained period of time" → "EASPT").
   (d) If dropping connectors would leave NO words at all, keep the title's words as they are and apply (c) to those.
   Use the SAME code every time the same element appears.
   - When a heading is written as `<Label> <id>: <Title>` — where `<Label>` is ANY structural word the document uses to name a level (e.g. Strand, Concept, Sub-Strand, Goal, Pillar, Unit, Theme, Section, Element, Standard, Domain, Benchmark, Component, Cluster, Foundation, Outcome, or whatever else this particular document uses) and `<id>` is the position identifier at that level (a number "1", a letter "A", a token "1.2") — the label-plus-id together is the element's `code`, written as the label, ONE space, then the id (e.g. "Strand 1", "Concept 2", "Goal A", "Pillar 1.2"). Whatever punctuation the heading used to separate the label from the id — a colon, hyphen, en/em dash — is layout and does NOT enter the code: "Strand: 1.0 — Listening and Speaking" gives code "Strand 1.0", never "Strand: 1.0". The `title` is ONLY the text after the colon (e.g. "Strand 1: Self-Awareness and Emotional Skills" → title "Self-Awareness and Emotional Skills"). This rule applies to EVERY structural-label heading word, not just the examples — never leave the `<Label> <id>:` prefix inside `title`, regardless of which word the document chose for `<Label>`.
   - A structural label word contributes NOTHING to the code on its own. It earns a place in the code only through the position identifier attached to it: "Strand 1" works as a code because "1" says WHICH strand. So when a heading names the level but supplies no position identifier — `<Label><separator><Title>` with nothing between the label and the title, whatever the separator (colon, hyphen, en/em dash, or just a space): e.g. "Sub-Strand — Vocabulary", "Concept - Curiosity and Interest", "Domain: Number Sense", "Goal — Working Memory" — the label is pure level-naming, exactly like the trailing structural noun below. Drop it and derive the code from the TITLE ALONE using the ≤5-char abbreviation rule ("Vocabulary" → "VOCA", "Curiosity and Interest" → "CI", "Number Sense" → "NS", "Working Memory" → "WM") — unless the document supplies a code for the element somewhere else, in a caption or through its descendants' codes, in which case that recovered code wins over any abbreviation ((ii)/(iii) above). Never abbreviate the label into the code and never prefix the code with it ("Sub-Strand — Vocabulary" → "VOCA", NOT "SS-V"; "Concept - Curiosity and Interest" → "CI", NOT "C-CI"), and never use the raw heading line as the code.
   - The same principle holds when the structural label appears as a TRAILING noun on the heading instead of a prefix: a heading like `<Title> <Label>` (e.g. "Social and Emotional Development Domain", "Language and Literacy Standard", "Physical Development Area", "Number Sense Strand") names a `<Title>` of a level the document calls `<Label>`. The structural noun is the level word, NOT part of the name — emit only the bare `<Title>` ("Social and Emotional Development", "Language and Literacy", "Physical Development", "Number Sense"). This applies regardless of which structural noun the document uses (Domain, Standard, Area, Strand, Section, Component, Cluster, Foundation, etc.). The same-named element may also appear elsewhere on the page as a running page header in ALL CAPS (e.g. "SOCIAL EMOTIONAL DEVELOPMENT STANDARD" repeated at the top of every page) — that running header is page typography, not a separate element and not a code; if you emit anything for it, normalize it back to the same bare title-cased `<Title>` so the two variants share the SAME `code` and the SAME `title`. The abbreviation rule above ("≤5-char uppercase abbreviation from the title") still applies WHEN the document leaves the element uncoded: derive the code from the BARE title (e.g. "Social Emotional Development" → "SED"), NEVER use the heading text itself or the structural noun as the code. If the document DOES code it — in a caption, or through the shared prefix of its descendants' codes — that recovered code wins ((ii)/(iii) above).
   - When a lettered list IS the leaf indicators (per rule 2), the `code` is JUST that item's letter, lowercased ("a", "b", "c", …) — exactly as the document orders them, regardless of any OCR casing. Do NOT prepend the parent strand/concept number (no "S1C1a"), and do NOT uppercase it (no bare "C"). The downstream parser supplies the parent's number; the detector only needs the consistent local letter.
5. `confidence`: 0.95+ if the depth map clearly applies; 0.80-0.94 if the chunk is ambiguous but the answer is likely; <0.70 if you are guessing.
6. `source_page`: page number from the `[Page N]` / `[Page N | x=…]` marker on that line.
7. `source_text`: the exact line(s) from the chunk you used. Copy verbatim, WITHOUT the leading `[Page N]` / `[Page N | x=…]` marker.
8. `description`: capture the element's COMPLETE descriptive/introductory prose, verbatim — EVERY sentence of a domain/strand/sub_strand introduction that appears in the chunk, not just the first sentence. Do NOT summarize, paraphrase, shorten, or stop at the first sentence. If the intro runs across several sentences or lines in the chunk, include all of them. (For an age-band column indicator, `description` is still only that one column's prose, per rule 3.) `description` holds only the text the element OWNS (rule 2a) — never a run that a heading or lead-in of its own has claimed; an element that owns no prose gets `null` for `description`, and that is the correct answer, not a gap to fill. Conversely, do not null out a `description` just because the text it owns reads like examples — unclaimed text under an element is that element's own.
   - ABSENCE IS `null`, NEVER `""`. When an element owns no prose, write `null` — not an empty string, not a string of spaces. `""` and `null` are two spellings of the same fact, and emitting both across a document makes the same absence irreconcilable downstream. Use `null` every time.

NEGATIVE EXAMPLES (do NOT do these):
- Do not emit "Indicators and Examples in the Context of Daily Routines" as a structural element. It is a section header. It is not an owner either: structural indicators follow it, so its claim is spent on them (rule 2a) — the example lines nested under each of those indicators belong to that indicator, not to this header.
- Do not merge "Early" and "Later" age columns into one indicator.
- Do not keep a structural label inside the title: "Strand 1: Self-Awareness" → title is "Self-Awareness", NOT "Strand 1: Self-Awareness".
- Do not keep a trailing structural noun inside the title: "Social and Emotional Development Domain" → title is "Social and Emotional Development", NOT "Social and Emotional Development Domain". "Language and Literacy Standard" → title is "Language and Literacy".
- Do not classify a numeric prefix ("1.", "2.") as `sub_strand` just because numeric-under-letter is sub_strand in some other doc — use the depth map.
- Do not truncate a multi-sentence domain/strand description to its first sentence — capture the entire introduction verbatim.
- When the depth map's leaf is a lettered list, do NOT drop or fold its letters: every "a./b./c." skill statement under a concept is its own indicator (e.g. under "Phonological Awareness" emit indicators "a","b","c","d","e","f","g", one per letter). Emit them even for concepts whose letters appear far from the concept heading in the chunk.
- When a lettered list is NOT the leaf — concrete anecdotes ("Chooses carrots over celery during mealtime.") sitting under an already-identified leaf indicator/foundation — do NOT promote them to indicators. Whether they land in that indicator's `description` is decided by rule 2a's ownership test, not by how anecdotal they sound.
- Do not drop text that no heading claimed. Anecdote lines running on directly beneath a leaf ("Acknowledges her own accomplishments and says, \"I can hit the ball.\"") — with no "Examples:"-style lead-in between them and the leaf — are that leaf's own `description`. A section header further UP the page does not change this: the leaf is the nearest element above the anecdotes, the gap between them is empty, so they are the leaf's. Emitting `null` there loses real content. Apply this identically to every such leaf on every page — two pages with the same layout must get the same answer.
- Do not paste a claimed run into the element above it. Under a "Child Behaviors" heading and a "The child may:" lead-in, the behaviors belong to that section — they go nowhere, and the indicator's `description` is `null`.
- Do not treat a phrase that merely announces an upcoming example list as an element or as a description. When the list follows that phrase directly, the phrase introduces illustrations and goes wherever the list goes: nowhere. When a structural element intervenes between the phrase and the list, the phrase's claim is already spent — the list is that element's own text (rule 2a).
- Do not fold a structural label into the code: "Sub-Strand — Vocabulary" → code "VOCA", never "SS-V", "SS-VOCA", or the whole heading line "Sub-Strand — Vocabulary". A label with no position identifier after it is not part of the code. Give the SAME element the SAME code on every chunk it appears in — never "VOCA" in one chunk and "SS-V" in another.
- Do not invent an abbreviation for an element the document has already coded elsewhere on the page. A group heading "Working Memory" captioned "Indicators (CD.WM)", or one whose indicators all read "CD.WM.PK1", "CD.WM.PK2", has code "CD.WM" — not "WM" (its last segment alone), and not "WORK" or "WM" derived from its title. The abbreviation is the LAST resort, for an element the document leaves genuinely uncoded; a code printed anywhere that points at the element beats it every time. The same holds for the level ABOVE that group: a domain heading with no printed code whose indicators read "CD.WM.PK1" and "CD.AT.PK1" has code "CD", not an abbreviation of its title.
- Do not let a recovered prefix reach past the level directly below it. If the chunk shows a domain heading and only ONE group beneath it, the indicators' shared prefix "CD.WM" is the GROUP's code, not the domain's — peel one segment per level and give the domain "CD". A prefix that equals the code of the element directly below it is a level too long.
- Do not read an ancestor's code out of a descendant's LABELLED id. Indicators coded "Foundation 1.7" and "Foundation 1.8" under a sub_strand "Grammar" do NOT give that sub_strand the code "Foundation 1": the label "Foundation" names the INDICATOR's level, so "1.7" is the indicator's own id and holds nothing for its parent. That sub_strand is uncoded, so it takes the title abbreviation "GRAM". Only bare dotted codes ("CD.WM.PK1", "I.A.2") carry an ancestor prefix.
- Do not carry the heading's separator punctuation into the code: "Strand: 1.0 — Listening and Speaking" → code "Strand 1.0", NOT "Strand: 1.0". Spell it the same way on every chunk — "Strand: 1.0" here and "Strand 2.0" there is the same construct written two ways, and the two no longer reconcile as one element.
- Do not back-form a parent heading out of a child's code. If the chunk begins mid-section with a leaf line like "A.B.1.b Child takes care of and manages classroom materials." and the "1. Behavior Control" heading it belongs under is not in this chunk, emit the leaf ALONE — do NOT also emit a sub_strand "1 / Behavior Control" whose only evidence is the "1" inside the leaf's code. Check yourself with `source_text`: if the only line you can cite for a heading is one of its children's lines, you did not see that heading and must not emit it. Note that you also cannot know its title — a title you supply from memory of an earlier chunk, or by guessing, is invented text (rule: never invent titles).
- Do not back-form a parent heading out of a child's code. If the chunk begins mid-section with a leaf line like "A.B.1.b Child takes care of and manages classroom materials." and the "1. Behavior Control" heading it belongs under is not in this chunk, emit the leaf ALONE — do NOT also emit a sub_strand "1 / Behavior Control" whose only evidence is the "1" inside the leaf's code. Check yourself with `source_text`: if the only line you can cite for a heading is one of its children's lines, you did not see that heading and must not emit it. Note that you also cannot know its title — a title you supply from memory of an earlier chunk, or by guessing, is invented text (rule: never invent titles).

OUTPUT — return ONLY a JSON array, starting with `[` and ending with `]`. No prose, no markdown, no commentary. Schema per element:
{{"level": "domain|strand|sub_strand|indicator", "code": "...", "title": "...", "description": "..." or null, "age_band": "..." or null, "confidence": 0.0-1.0, "source_page": N, "source_text": "..."}}

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


def canonicalize_depth_map_levels(depth_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Force `canonical_level` to be a pure function of a depth's POSITION in the
    document's own nesting, so the depth→level mapping cannot drift between
    runs or between documents.

    The canonical levels are filled from the top down and dropped from the
    bottom of the middle: first depth is `domain`, deepest is `indicator`, the
    depth directly under domain is `strand`, and anything between that and the
    leaf is `sub_strand`. A 3-level document is therefore
    domain > strand > indicator — it has NO sub_strand.

    This is deterministic, document-agnostic post-processing: it reads only the
    number and ordering of depths the LLM reported, never the document's own
    label words. Mutates and returns `depth_map`.
    """
    depths = depth_map.get("doc_depths")
    if not isinstance(depths, list) or len(depths) < 2:
        return depth_map

    ordered = sorted(
        (d for d in depths if isinstance(d, dict)),
        key=lambda d: (d.get("depth") if isinstance(d.get("depth"), int) else 0),
    )
    last = len(ordered) - 1
    for i, entry in enumerate(ordered):
        if i == last:
            level = "indicator"
        elif i == 0:
            level = "domain"
        elif i == 1:
            level = "strand"
        else:
            level = "sub_strand"
        if entry.get("canonical_level") != level:
            logger.info(
                f"Depth map: correcting depth={entry.get('depth')} "
                f"{entry.get('canonical_level')!r} → {level!r} "
                f"({len(ordered)}-level document)"
            )
            entry["canonical_level"] = level
    return depth_map


def infer_depth_map(
    blocks: List[TextBlock],
    metrics_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pass 1: ask the LLM to describe the document's nesting hierarchy.

    Returns the parsed depth_map dict, or None on failure (caller should
    fall back to no-depth-map mode rather than aborting detection).

    ABLATION HOOK (arXiv paper Task 3). `Config.DEPTH_MAP_ENABLED` is checked
    HERE rather than at the call sites on purpose: `infer_depth_map` has two
    production callers — `detect_structure` (the direct path, which is what
    `eval_detector` runs) and `detection_batching.prepare_detection_batches`
    (the batched path) — and gating only one would leave the other unablated,
    making any comparison between them meaningless. One gate at the source
    cannot be half-applied.

    Returning None is deliberately the SAME signal an inference failure
    already produces, so no caller needs to learn a new state: both callers
    already treat None as "run without a depth map", which is the system's
    real graceful-degradation path rather than a strawman written for the
    paper. `build_detection_prompt` has carried a `depth_map=None` branch all
    along.
    """
    if not Config.DEPTH_MAP_ENABLED:
        logger.warning(
            "DEPTH_MAP_ABLATION: Pass-1 depth-map inference DISABLED via "
            "ELS_DEPTH_MAP_ENABLED. Detection will run without a depth map. "
            "This is not the production default — if you did not intend an "
            "ablation run, unset the variable."
        )
        return None

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

    canonicalize_depth_map_levels(depth_map)

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
    # `description` is deliberately NOT required: it is Optional on
    # DetectedElement and absent for most headings, so a model that answers the
    # "absence is null" rule by omitting the key entirely must not cost us the
    # whole element. Every other field is load-bearing and stays required.
    required_fields = ['level', 'code', 'title', 'confidence', 'source_page', 'source_text']
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


def _is_title_grounded(element: DetectedElement) -> bool:
    """
    True when a HEADING element's title actually appears in the text it cites.

    Guards against a fabricated parent. A chunk that opens mid-section shows
    the LLM child codes whose segments name their ancestors — an indicator
    coded ``PK3.I.B.1.b`` announces that a sub_strand ``1`` exists — and the
    model sometimes back-forms that ancestor into an element even though its
    heading line was left behind in the previous chunk. The tell is always the
    same: the invented element's ``source_text`` is the CHILD's line, so its
    title is nowhere in the text it claims to have read. A real heading is
    transcribed off the page, so its title is always present in its own
    ``source_text``.

    Scoped to domain/strand/sub_strand. Indicators are exempt, and must be: on
    a side-by-side age-band layout, prompt rule 3 gives every column indicator
    the row's shared header as its ``title`` while ``source_text`` holds only
    that one column's cell — so a correct column indicator legitimately fails
    this test. Fabrication is a heading-level failure anyway; nothing invents a
    leaf out of its own code.

    Comparison is on letters and digits alone (see ``_GROUNDING_STRIP_RE``), so
    only a genuinely absent title fails rather than a re-punctuated one.
    """
    if element.level == HierarchyLevelEnum.INDICATOR:
        return True
    title = _GROUNDING_STRIP_RE.sub("", (element.title or "").lower())
    if not title:
        return True
    source = _GROUNDING_STRIP_RE.sub("", (element.source_text or "").lower())
    return title in source


def _canonicalize_code(code: Any) -> Any:
    """Fold a `<Label>: <id>` code to the canonical `<Label> <id>`.

    Prompt rule 4 makes a heading's label-plus-id the element's code, but the
    LLM sometimes carries the heading's own colon into it, and does so
    inconsistently across chunks — the same strand arriving as "Strand: 1.0"
    from one chunk and "Strand 2.0" from another. Two spellings of one
    construct defeat the cross-chunk reconciliation in ``_dedup_elements``,
    which keys on the code, and they compose into two different
    ``standard_id``s downstream.

    This is the same class of fix as ``_normalize_age_band``: a deterministic
    canonicalization of an already-clean field whose only variation is
    transcription noise. It reads the code's SHAPE, not its vocabulary, so it
    is document-agnostic (see ``_CODE_LABEL_SEPARATOR_RE``). Anything without
    that shape is returned untouched."""
    if not isinstance(code, str):
        return code
    return _CODE_LABEL_SEPARATOR_RE.sub(r"\1 \2", code.strip())


def derive_code_from_title(title: Any) -> Optional[str]:
    """Run prompt rule 4's abbreviation procedure deterministically.

    A faithful transcription of rule 4 (a)-(d): split on whitespace and slashes
    (a hyphenated compound stays ONE word), drop connector words, then a single
    remaining content word yields its first 4 letters and several yield their
    initials capped at 5. Returns None when the title yields nothing.

    This exists because the procedure is a deterministic string algorithm and
    the LLM samples it. Measured on Kentucky (2026-08-01, three detector runs
    at temperature 0 on one frozen extraction): 11 of 44 elements — 25% —
    received a different code on at least one run, while level, source_page and
    age_band never varied once. The churn is not near-misses: one run emitted a
    4-character code, another transposed two initials, several kept a connector
    the rule says to drop. Since ``standard_id`` is
    ``{country}-{state}-{year}-{indicator_code}``, that is a different primary
    key for the same standard depending on which run wrote it.

    Pairs with the prompt rule rather than replacing it — the same posture
    ``_canonicalize_code`` and ``_normalize_age_band`` take, and for the same
    reason: a prompt rule lowers the error rate but cannot drive it to zero,
    and a primary key needs zero. It reads only the SHAPE of a title, never any
    document's vocabulary, so it is document-agnostic.
    """
    if not isinstance(title, str):
        return None
    words = []
    for raw in _CODE_WORD_SPLIT_RE.split(title):
        word = _CODE_WORD_STRIP_RE.sub("", raw)
        if word:
            words.append(word)
    if not words:
        return None
    # (b) drop connectors; (d) if that leaves nothing, keep the words as they are
    content = [w for w in words if w.lower() not in _CODE_CONNECTORS] or words
    if len(content) == 1:
        return content[0][:DERIVED_CODE_SINGLE_WORD_LEN].upper() or None
    return "".join(w[0] for w in content)[:DERIVED_CODE_MAX_LEN].upper() or None


def _is_code_grounded(code: Any, source_text: Any) -> bool:
    """True when the code appears in the text the element cites.

    Rule 4 branches on whether the document supplies a code: a document code is
    used as-is, and only in its absence does the model invent an abbreviation.
    Downstream we see just the emitted element, so this recovers which branch
    was taken from the evidence the element carries — a document code was read
    off the page and is therefore present in ``source_text`` ("Benchmark 1.1",
    "I.A.2", "1.0", a list letter "a"), whereas an invented abbreviation is
    derived from the title and appears nowhere in it ("EASPT" is not in
    "Engages in an activity for a sustained period of time").

    The same evidence ``_is_title_grounded`` uses, applied to the other field.
    Matching is case-SENSITIVE and word-bounded on purpose: a case-insensitive
    substring test would read the ordinary English word "as" as grounding a
    derived code "AS", and would find a two-letter code inside longer words.

    Both sides get the ``<Label>: <id>`` → ``<Label> <id>`` fold that
    ``_canonicalize_code`` applies, so the two passes cannot disagree about the
    same heading. Without it a code canonicalized to "Strand 1.0" would fail to
    match the "Strand: 1.0" actually printed on the page, and a real document
    code would be mistaken for an invented one.
    """
    if not isinstance(code, str) or not code.strip():
        return False
    if not isinstance(source_text, str) or not source_text:
        return False
    needle = _CODE_LABEL_COLON_RE.sub(" ", code.strip())
    haystack = _CODE_LABEL_COLON_RE.sub(" ", source_text)
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _resolve_code(code: Any, title: Any, source_text: Any) -> Any:
    """Keep a document-supplied code; recompute an invented one deterministically.

    Scoped to the invented case by design — a code the document actually prints
    is authoritative and is never overwritten, however unlike our abbreviation
    scheme it looks.

    Two independent guards, because grounding alone is not sufficient. A code is
    recomputed only if it could have come from rule 4's abbreviation branch in
    the first place — that branch emits UPPERCASE letters and nothing else, so a
    code carrying a digit, a separator or a lowercase letter is positional and
    is left alone. That guard is what protects rule 4's other branch, the
    lettered leaf whose code is just its list letter ("a", "b", "c"): the model
    sometimes transcribes such an item's ``source_text`` without the "a. "
    prefix, and grounding alone would then read a real list code as invented and
    overwrite it with an abbreviation of the title (observed on AZ: 8 of 9
    lettered leaves kept the prefix, the ninth did not).
    """
    if not _DERIVABLE_CODE_RE.match(str(code or "")):
        return code
    if _is_code_grounded(code, source_text):
        return code
    derived = derive_code_from_title(title)
    if derived is None or derived == code:
        return code
    logger.debug(
        f"Recomputed invented code {code!r} → {derived!r} from title {str(title)[:60]!r}"
    )
    return derived


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
    
    age_band = _normalize_age_band(elem_data.get('age_band'))

    title = _strip_label_prefix(elem_data['title'])

    return DetectedElement(
        level=level,
        code=_resolve_code(
            _canonicalize_code(elem_data['code']), title, elem_data['source_text']
        ),
        title=title,
        # Pass the raw value through: DetectedElement folds a missing/blank
        # description to None (models._blank_to_none).
        description=elem_data.get('description'),
        confidence=confidence,
        source_page=elem_data.get('source_page', default_page),
        source_text=elem_data['source_text'],
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
            if not _is_title_grounded(element):
                logger.warning(
                    f"Element {idx}: ungrounded {element.level.value} "
                    f"'{element.code} - {element.title[:50]}' — its title does not "
                    f"appear in its own source_text ({element.source_text[:80]!r}); "
                    f"dropping as a back-formed parent"
                )
                continue
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


def _normalize_title(title: Optional[str]) -> str:
    """Whitespace- and case-normalized title, for duplicate comparison only."""
    return " ".join((title or "").lower().split())


def _is_truncated_prefix(shorter: str, longer: str) -> bool:
    """
    True when ``shorter`` looks like a chunk-truncated twin of ``longer``.

    A chunk boundary can cut an element's text mid-sentence, so the same
    element is emitted once truncated (chunk N, whose text ran out) and once
    complete (chunk N+1, which saw it whole). The truncated twin is always a
    strict PREFIX of the complete one.

    Two guards keep genuinely distinct siblings apart — "Physical Development"
    and "Physical Development and Health" are different elements, not a
    truncation pair:

    * the prefix must be SUBSTANTIAL (> ``MIN_PREFIX_TITLE_CHARS`` characters),
      so short label-like titles never trigger it; and
    * the prefix must end on a WORD BOUNDARY in the longer title, i.e. the
      longer title continues with a separator rather than finishing a word
      that the shorter one cut in half.

    Caller supplies the remaining guards (same level, age_band, code, and
    owning domain).
    """
    if len(shorter) <= MIN_PREFIX_TITLE_CHARS:
        return False
    if shorter == longer or not longer.startswith(shorter):
        return False
    return not longer[len(shorter)].isalnum()


def _reconcile_age_band_drift(elements: List[DetectedElement]) -> List[DetectedElement]:
    """
    Fold two spellings of ONE age-band column back into a single label.

    Chunk N reads a column header as "PK3" while chunk N+1 reads the same
    header as "PK3 Outcome". Both are correct transcriptions of the same
    column, but ``_dedup_elements`` keys identity on ``age_band``, so the two
    spellings split one column in two: the overlap copies never collapse, and
    a truncated twin never meets its complete form in Pass 2. Downstream the
    survivors become separate standards that collide on ``standard_id`` —
    observed on TX as four colliding ids across 29 standards holding 25
    distinct keys.

    Two conditions must BOTH hold before folding, which is what keeps this
    document-agnostic rather than a TX rule in disguise:

    1. **Token-prefix shape.** One label's tokens are a leading run of the
       other's ("PK3" ⊂ "PK3 Outcome"). This never fires on genuinely distinct
       bands — CA's "Early (3 to 4 ½ Years)" / "Later (4 to 5 ½ Years)" and its
       "Discovering" / "Developing" / "Broadening" are unrelated under it.
    2. **Same-element evidence.** Some element carries both labels while being
       otherwise identical (same level, code, title, page). That is what
       distinguishes ONE column transcribed twice from two real bands that
       merely share a prefix — a document with distinct "Age 3" and
       "Age 3 to 4" columns has the prefix shape but never the evidence, so it
       is left alone.

    The longer label folds into the shorter, consistent with prompt rule 4
    treating a trailing structural noun as the level word rather than part of
    the name ("PK3 Outcome" is the PK3 band in an Outcome column).
    """
    bands = {e.age_band for e in elements if e.age_band}
    if len(bands) < 2:
        return elements

    # Condition 1 — token-prefix candidates, longer -> shorter.
    candidates: Dict[str, str] = {}
    for short in bands:
        for long in bands:
            if short == long:
                continue
            st, lt = short.split(), long.split()
            if len(st) < len(lt) and lt[:len(st)] == st:
                # Keep the SHORTEST valid target if several prefixes match.
                if long not in candidates or len(candidates[long].split()) > len(st):
                    candidates[long] = short
    if not candidates:
        return elements

    # Condition 2 — an otherwise-identical element carrying both labels.
    by_identity: Dict[tuple, set] = {}
    for e in elements:
        key = (e.level.value, e.code, _normalize_title(e.title), e.source_page)
        by_identity.setdefault(key, set()).add(e.age_band)

    confirmed = {
        long: short
        for long, short in candidates.items()
        if any(short in seen and long in seen for seen in by_identity.values())
    }
    if not confirmed:
        return elements

    for long, short in sorted(confirmed.items()):
        logger.info(f"Age-band drift: folding {long!r} -> {short!r}")

    return [
        e.model_copy(update={"age_band": confirmed[e.age_band]})
        if e.age_band in confirmed else e
        for e in elements
    ]


def _splice_overlapping_prose(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Join two partial views of ONE passage on the text they share.

    Chunks overlap, so an element's prose can be split such that NEITHER chunk
    holds it whole: the earlier chunk has the head and the later chunk — which
    opens part-way through the passage — has the tail. Picking the longer of
    the two then silently drops one end (observed on NV's Science domain intro:
    chunk 2 carried chars 0-2410, chunk 3 carried chars ~540-3500, and the
    longer one won while starting mid-sentence).

    Because the two views come from an OVERLAP, the shared span is present in
    both: the tail of ``a`` is the head of ``b``. Splicing there reconstructs
    the passage exactly, with no invented or duplicated text.

    Returns the spliced text, or ``None`` when the two share no anchor and the
    caller must fall back. Containment is handled first — a strict superset
    needs no splice. Matching is exact and requires a run of at least
    ``_MIN_PROSE_OVERLAP`` characters, long enough that a shared sentence
    opener or boilerplate clause cannot fake an anchor.
    """
    if not a:
        return b
    if not b:
        return a
    if b in a:
        return a
    if a in b:
        return b
    if len(b) < _MIN_PROSE_OVERLAP:
        return None
    probe = b[:_MIN_PROSE_OVERLAP]
    idx = a.find(probe)
    while idx != -1:
        # a[idx:] is a's tail; it anchors only if b actually continues it.
        if b.startswith(a[idx:]):
            return a + b[len(a) - idx:]
        idx = a.find(probe, idx + 1)
    return None


def _merge_duplicate(keep: DetectedElement, other: DetectedElement) -> DetectedElement:
    """
    Fold ``other`` into ``keep``, retaining the richer content of the two.

    Used for both duplicate shapes: an exact repeat across an overlap, and a
    truncated/complete pair. The winner keeps the LONGER title (a truncated
    twin is by definition the shorter one) and the higher confidence.

    The description is RECONCILED rather than chosen: two chunks can hold
    different partial views of one passage, so they are spliced on the text
    they share (:func:`_splice_overlapping_prose`). Longest-wins is only the
    fallback, for the case where the two share no anchor — it assumes the
    longer view is the more complete one, which holds for a plain repeat but
    NOT for a head/tail split.

    ``keep`` is passed first because it is the earlier of the two in document
    order, so it supplies the head and ``other`` the tail. The reversed splice
    is attempted too, since chunk-overlap re-emission can invert that order.
    """
    title = keep.title if len(keep.title or "") >= len(other.title or "") else other.title
    description = (
        _splice_overlapping_prose(keep.description, other.description)
        or _splice_overlapping_prose(other.description, keep.description)
        or (
            keep.description
            if len(keep.description or "") >= len(other.description or "")
            else other.description
        )
    )
    return keep.model_copy(update={
        "title": title,
        "description": description,
        "confidence": max(keep.confidence, other.confidence),
    })


def _dedup_elements(elements: List[DetectedElement]) -> List[DetectedElement]:
    """
    Drop duplicate elements produced by chunk overlap.

    Adjacent chunks intentionally overlap (DEFAULT_OVERLAP_TOKENS) so elements
    at a chunk boundary can be re-emitted by both chunks — in two shapes:

    1. **Exact repeat.** The same element appears whole in both chunks, but the
       LLM may label it with a different code each time ("SED" then "I" for one
       domain, "1" then "1.b" for one sub_strand). Codes are reconciled FIRST,
       by the shared cross-chunk machinery in ``parser.normalize_element_codes``,
       so the two instances become byte-identical and collapse.
    2. **Truncated twin.** The boundary cut the element's text, so chunk N
       emitted a prefix of the title and chunk N+1 emitted it whole. Handled by
       prefix dominance (see ``_is_truncated_prefix``): the longer title wins.

    Neither pass may key on title alone: two different domains can legitimately
    hold same-titled children — CA's ELD and FLD domains each have a
    "Vocabulary" sub_strand and a "Listening and Speaking" strand — and those
    must NOT be collapsed into one. Pass 1 separates them with the element's
    OWN page and code (see below); Pass 2 uses the document-order domain scope
    from ``parser.assign_domain_scopes``.

    Order is preserved by first appearance so the document-ordered structure
    (and downstream domain context) is intact. That matters more than it looks:
    the parser resolves parentage by "the most-recent preceding sub_strand in
    document order", so an element that de-duplication moves — or a header whose
    surviving copy sits at the wrong position — silently reparents everything
    after it.
    """
    if not elements:
        return elements

    # Reconcile cross-chunk code drift first — reusing the existing machinery
    # rather than re-deriving it here — so instances of one entity that differ
    # ONLY in code become identical and can collapse below.
    elements = normalize_element_codes(elements)
    # Age-band spellings must be reconciled BEFORE Pass 1: age_band is part of
    # the identity key below, so two spellings of one column would otherwise
    # survive as two elements no matter what the rest of this function does.
    elements = _reconcile_age_band_drift(elements)
    scopes = assign_domain_scopes(elements)

    # Pass 1 — collapse exact repeats of the same OCCURRENCE.
    #
    # The key turns on SOURCE_PAGE plus a CODE-derived domain. Both are
    # properties the element carries itself, and that is deliberate: an
    # overlap-repeated element prints the identical `[Page N]` marker in both
    # chunks, whereas a position-derived domain scope depends on the very list
    # ordering that chunk overlap perturbs. Keying identity on document order is
    # circular, and it failed in both directions:
    #
    #   * an order-derived scope SPLIT one occurrence in two whenever the
    #     re-emission landed past a later domain heading — CO's page-4 Gross
    #     Motor indicators, re-emitted from the head of a chunk whose overlap
    #     had left their strand header behind, scored domain SED instead of PDH
    #     and survived as three parentless rows the parser could only file under
    #     "UNKNOWN";
    #   * dropping source_page MERGED two genuinely distinct occurrences
    #     whenever a document names an element twice on different pages. AZ
    #     lists every Concept on a page-4 contents page AND again as its own
    #     section header on pages 8-14; collapsing those kept the contents-page
    #     copy, relocating all seven headers to the front of the document and
    #     leaving 37 indicators with no preceding parent.
    #
    # Domains are exempt from the page component: they are the one level that
    # reconciles safely on title alone (see parser.canonical_domain_codes), so a
    # domain re-stated on a later page still collapses to one row.
    best: Dict[tuple, tuple[DetectedElement, Optional[str]]] = {}
    order: List[tuple] = []
    identity_scopes = code_domain_scopes(elements)
    for el, scope, identity_scope in zip(elements, scopes, identity_scopes):
        key = (
            el.level.value,
            _normalize_title(el.title),
            el.age_band or None,
            None if el.level == HierarchyLevelEnum.DOMAIN else el.source_page,
            identity_scope,
        )
        if key not in best:
            best[key] = (el, scope)
            order.append(key)
        else:
            kept, kept_scope = best[key]
            best[key] = (_merge_duplicate(kept, el), kept_scope)
    survivors = [best[k][0] for k in order]
    survivor_scopes = [best[k][1] for k in order]

    # Pass 2 — prefix dominance: collapse a truncated twin into its complete
    # form. Only within one (level, age_band, code, domain) group: a truncated
    # twin is the SAME element, so the document code the LLM read off the page
    # is identical for both halves.
    groups: Dict[tuple, List[int]] = {}
    for idx, (el, scope) in enumerate(zip(survivors, survivor_scopes)):
        groups.setdefault(
            (el.level.value, el.age_band or None, el.code, scope), []
        ).append(idx)

    absorbed: Dict[int, int] = {}  # truncated index -> surviving index
    for members in groups.values():
        if len(members) < 2:
            continue
        # Longest title first, so a truncated twin is absorbed by the most
        # complete form available rather than by another partial one.
        ranked = sorted(members, key=lambda i: -len(_normalize_title(survivors[i].title)))
        for pos, short_idx in enumerate(ranked):
            short_title = _normalize_title(survivors[short_idx].title)
            for long_idx in ranked[:pos]:
                if long_idx in absorbed:
                    continue
                if _is_truncated_prefix(short_title, _normalize_title(survivors[long_idx].title)):
                    absorbed[short_idx] = long_idx
                    break

    if absorbed:
        # The complete form is the base (it carries the untruncated
        # source_text); it takes the EARLIEST of the two document positions so
        # the element stays where it first appears.
        merged: Dict[int, DetectedElement] = {}
        emit_at: Dict[int, int] = {}
        for short_idx, long_idx in sorted(absorbed.items()):
            logger.info(
                f"Collapsing truncated chunk-boundary twin "
                f"{survivors[short_idx].level.value} {survivors[short_idx].code!r} "
                f"{survivors[short_idx].title[:60]!r} into "
                f"{survivors[long_idx].title[:60]!r}"
            )
            merged[long_idx] = _merge_duplicate(
                merged.get(long_idx, survivors[long_idx]), survivors[short_idx]
            )
            emit_at[long_idx] = min(emit_at.get(long_idx, long_idx), short_idx)

        rebuilt: List[DetectedElement] = []
        for i, el in enumerate(survivors):
            target = absorbed.get(i, i if i in merged else None)
            if target is None:
                rebuilt.append(el)
            elif emit_at[target] == i:
                rebuilt.append(merged[target])
        survivors = rebuilt

    dropped = len(elements) - len(survivors)
    if dropped:
        logger.info(f"De-duplicated {dropped} overlap-repeated elements "
                    f"({len(elements)} → {len(survivors)})")
    return survivors


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
        DetectionResult with detected elements and status
    """
    logger.info(f"Starting structure detection for document: {document_s3_key}")
    logger.info(f"Input: {len(blocks)} text blocks")

    if not blocks:
        logger.error("No text blocks provided")
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
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

        # Log summary by level
        level_counts = {}
        for elem in all_elements:
            level_counts[elem.level.value] = level_counts.get(elem.level.value, 0) + 1

        logger.info(
            f"Detection complete: {len(all_elements)} total elements detected"
        )
        logger.info(f"Elements by level: {level_counts}")

        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=all_elements,
            status="success",
            error=None
        )

    except Exception as e:
        logger.error(f"Structure detection failed: {e}", exc_info=True)
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            status="error",
            error=str(e)
        )
