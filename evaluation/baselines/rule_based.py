"""Rule-based structure detector — the arXiv paper's baseline (Task 4).

⚠️ THIS IS A THROWAWAY BASELINE, NOT PIPELINE CODE. It exists so the paper can
report what a competent regex/heuristic extractor achieves on the same
documents, graded by the same suite against the same goldens. Nothing here may
migrate into ``src/els_pipeline/`` — CLAUDE.md's design direction makes exactly
this kind of logic a regression when it appears in ``detector.py``.

Interface parity with ``els_pipeline.detector.detect_structure``: it takes the
same ``list[TextBlock]`` and returns the same ``DetectionResult``, so
``eval_detector``'s grading path consumes it unchanged.

## What it is allowed to know

Document-agnostic signals only. There is no state name anywhere in this file
and no branch keyed to one — the same reason ``detector.py`` may not carry one.
The signals are the ones the Task 4 handoff names, plus the two the extraction
turns out to carry:

  1. **numbering** — ``1.``, ``1.1``, ``a.``, ``I.A.2``, ``PK3.I.A.2``; nesting
     depth is the level cue.
  2. **structural label words** — ``Domain``/``Strand``/``Standard``/
     ``Benchmark``/``Indicator``/``Concept``/``Foundation``/…, mapped to a
     level by a table frozen before scoring (see ``LABEL_LEVELS``).
  3. **typography** — ALL-CAPS lines, and font size read off the bounding-box
     height relative to the page median.
  4. **layout** — bounding-box ``Left`` gives indentation and, clustered, gives
     columns; ``Width`` distinguishes a full-width paragraph from a column cell.

(3) and (4) are available because Textract's blocks carry ``geometry``. The
June 2026 predecessor of this file (``evaluation/baseline_detector.py``, deleted
in this task) used regex alone and never looked at geometry; column-aware
reading order is most of what separates a fair baseline from a straw man on the
multi-column state documents.

## The frozen-mapping discipline

``LABEL_LEVELS`` and the numbering-depth mapping were written down BEFORE any
state was scored, from the canonical schema's own semantics
(domain > strand > sub_strand > indicator), and were not revised afterwards. A
label table tuned per document would make the baseline look better while
measuring nothing — the same overfitting failure CLAUDE.md documents for the
detector. Development used only the four golden states (AZ, CA, CO, TX); NV and
KY were not inspected or scored until the recorded run.

Mapping a label word to a level is, of course, exactly the strategy the paper's
title argues against ("classify by position, not by label"). That is the point:
the baseline is the concrete form of the alternative.
"""

from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from els_pipeline.detector import derive_code_from_title
from els_pipeline.models import (
    DetectedElement,
    DetectionResult,
    HierarchyLevelEnum,
    TextBlock,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Frozen tables — see the module docstring's "frozen-mapping discipline" note.
# --------------------------------------------------------------------------

#: Structural label word -> canonical level. Written from the schema's own
#: semantics before any state was scored. A word absent here contributes no
#: level evidence at all rather than a guess.
LABEL_LEVELS: Dict[str, HierarchyLevelEnum] = {
    "domain": HierarchyLevelEnum.DOMAIN,
    "area": HierarchyLevelEnum.DOMAIN,
    "strand": HierarchyLevelEnum.STRAND,
    "standard": HierarchyLevelEnum.STRAND,
    "goal": HierarchyLevelEnum.STRAND,
    "substrand": HierarchyLevelEnum.SUB_STRAND,
    "sub-strand": HierarchyLevelEnum.SUB_STRAND,
    "concept": HierarchyLevelEnum.SUB_STRAND,
    "topic": HierarchyLevelEnum.SUB_STRAND,
    "component": HierarchyLevelEnum.SUB_STRAND,
    "benchmark": HierarchyLevelEnum.SUB_STRAND,
    "indicator": HierarchyLevelEnum.INDICATOR,
    "foundation": HierarchyLevelEnum.INDICATOR,
    "objective": HierarchyLevelEnum.INDICATOR,
    "skill": HierarchyLevelEnum.INDICATOR,
    "outcome": HierarchyLevelEnum.INDICATOR,
    "example": HierarchyLevelEnum.INDICATOR,
}

#: Numbering nesting depth -> canonical level, for a heading carrying no label
#: word. Depth 1 is a strand rather than a domain because a domain is
#: overwhelmingly a titled heading, not a numbered one; a depth-1 numbered item
#: under a domain heading is its first subdivision.
DEPTH_LEVELS: Dict[int, HierarchyLevelEnum] = {
    1: HierarchyLevelEnum.STRAND,
    2: HierarchyLevelEnum.SUB_STRAND,
    3: HierarchyLevelEnum.INDICATOR,
}

#: A lone lettered item (``a.``, ``b)``) is a leaf enumerating examples under
#: whatever precedes it.
LETTER_ITEM_LEVEL = HierarchyLevelEnum.INDICATOR

#: An age/column token leading a numbering path (``PK3.I.A.2``). Recognized by
#: shape — letters then digits — never by a list of known tokens.
AGE_PREFIX_RE = re.compile(r"^[A-Z]{1,4}\d{1,2}$")

# --------------------------------------------------------------------------
# Layout constants. All are fractions of page width/height (Textract geometry
# is normalized), so they carry no page-size or document assumption.
# --------------------------------------------------------------------------

#: A block at least this wide spans the text column and acts as a band break in
#: reading-order reconstruction.
SPAN_WIDTH_FRAC = 0.55

#: Horizontal gap between sorted left-edges that starts a new column. Set
#: below the narrowest real column step seen in the corpus (0.09) and above the
#: widest hanging indent inside one column (0.014), so an indented continuation
#: stays with its own column while a neighbouring column separates.
COLUMN_GAP_FRAC = 0.06

#: Vertical gap, in multiples of the local line height, beyond which two lines
#: are separate units rather than a wrapped continuation.
LINE_GAP_MULTIPLE = 1.9

#: Left-edge tolerance for treating a line as the wrapped continuation of the
#: one above it. Deliberately tighter than COLUMN_GAP_FRAC: a wrap is flush or
#: slightly indented, never most of a column away.
CONTINUATION_ALIGN_FRAC = 0.03

#: A wrapped continuation is set in the SAME type as the line it continues.
#: Without this a display heading swallows the smaller column headers beneath
#: it ("Physical Development & Health Examples Children may.").
CONTINUATION_SIZE_TOLERANCE = 0.25

#: A display heading must clear BOTH the page median by this factor and the
#: page's 90th-percentile line height. The percentile alone admits ordinary
#: body text on a page of uniform type; the ratio alone misses a heading on a
#: page whose body is unusually varied.
DISPLAY_SIZE_FACTOR = 1.10

#: A line set below this fraction of the page's median line height is
#: micro-type — a running header, a sidebar tab, a footnote — not content. The
#: ratio is what matters, not the margin: Colorado prints its domain-navigation
#: tabs at 55% of body size and they reach as far down as 0.086 of the page,
#: well clear of any plausible margin band.
FURNITURE_SIZE_FRAC = 0.72

#: Page furniture: a line this short is a folio, header or footer fragment.
FURNITURE_MAX_CHARS = 3

#: Cap on an emitted title, mirroring the detector's own practical bound.
MAX_TITLE_CHARS = 300


# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

#: A dotted/segmented numbering path: ``1.``, ``1.1``, ``I.A.2``, ``PK3.I.A.2``,
#: ``2.0``. Group 1 is the path, group 2 the separator that closed it.
#:
#: ⚠️ The separator is OPTIONAL, and that is load-bearing: Texas prints its
#: leaf codes as ``PK4.I.A.1 Child is aware of…`` with no punctuation after the
#: last segment, so a mandatory terminator matched none of its 45 indicators.
#: A bare ``A `` or ``1 `` with no terminator is far too common in prose to
#: accept, so ``_heading_signal`` requires such a path to be multi-segment.
NUMBER_PATH_RE = re.compile(
    r"^\s*("
    r"(?:[A-Z]{1,4}\d{1,2}\.)?"          # optional age/column prefix, e.g. PK3.
    r"(?:\d{1,3}|[IVXL]{1,5}|[A-Z])"     # first segment
    r"(?:\.(?:\d{1,3}|[IVXL]{1,5}|[A-Za-z]))*"  # further dotted segments
    r")"
    r"([.):]?)\s+(?=\S)"
)

#: A lone lettered list item: ``a.``, ``b)``, ``c:``.
LETTER_ITEM_RE = re.compile(r"^\s*([a-z])[.):]\s+(?=\S)")

#: ``<Label> <id>:`` / ``<Label> <id> `` / bare ``<Label>:`` heading. Group 1 is
#: the label word, group 2 the identifier if present.
#:
#: The closing separator may be punctuation OR plain whitespace, because
#: California prints "Foundation 1.1 Curiosity and Interest" with nothing after
#: the identifier. Requiring punctuation made the pattern backtrack to a
#: one-segment identifier and hand the rest of the id to the title
#: (``Foundation 1`` + ``1 Curiosity and Interest``). It may NOT be empty — one
#: of the two must be present, or "Standardized" parses as ``Standard`` + "ized".
LABEL_HEADING_RE = re.compile(
    r"^\s*(" + "|".join(sorted((re.escape(w) for w in LABEL_LEVELS), key=len, reverse=True)) + r")"
    r"(?:\s+([0-9IVXL]+(?:\.[0-9A-Za-z]+)*|[A-Z]))?"
    r"(?:\s*[:.—–-]\s*|\s+)(?=\S)",
    re.IGNORECASE,
)

#: Leading punctuation left behind after an identifier is lifted out of a
#: heading's remainder ("1.0 — Motivation to Learn" -> "Motivation to Learn").
LEADING_SEPARATOR_RE = re.compile(r"^[\s:.—–-]+")

#: An age-band COLUMN HEADER: a short line ending in a parenthesized numeric
#: range, e.g. "Early (3 to 4 ½ Years)" / "Later (4 to 5 1/2 Years)".
#:
#: Recognized by SHAPE, never by vocabulary — there is no list of band names
#: here, because a list of band names is a per-document rule. A parenthesized
#: span that opens with a digit and sits at the end of a short line is an age
#: qualifier in any document that uses one.
AGE_BAND_HEADER_RE = re.compile(r"^.{0,40}\(\s*\d[^)]{0,30}\)\s*$")

#: Longest a line may be and still read as a column header rather than prose.
AGE_BAND_HEADER_MAX_CHARS = 60

#: A trailing structural noun on an otherwise-titled heading
#: ("SOCIAL EMOTIONAL DEVELOPMENT STANDARD", "…Development Domain").
#:
#: ⚠️ This is a STRICT SUBSET of LABEL_LEVELS, and it has to be. Several label
#: words are ordinary content nouns that end real titles — Arizona's strand is
#: "Self-Awareness and Emotional Skills" and Colorado's are "…Knowledge &
#: Skills" — so stripping every label word from the end of a title deletes part
#: of the name. A word qualifies here only if it names a SECTION rather than a
#: subject: "Domain", "Standard", "Strand", "Area". Leading labels are not
#: affected, because there a colon or an identifier disambiguates.
TRAILING_LABEL_WORDS = ("domain", "standard", "strand", "area")

TRAILING_LABEL_RE = re.compile(
    r"\s+(" + "|".join(re.escape(w) for w in TRAILING_LABEL_WORDS) + r")s?\s*$",
    re.IGNORECASE,
)

#: Sentence-ish terminator used to split a title from trailing prose.
COLON_SPLIT_RE = re.compile(r"^(?P<title>[^:]{2,120}):\s+(?P<rest>\S.*)$", re.DOTALL)

#: Page furniture by shape: a bare folio, or a line that is only digits/roman.
FOLIO_RE = re.compile(r"^\s*[\divxlcIVXLC–—-]{1,8}\s*$")


# --------------------------------------------------------------------------
# Layout reconstruction
# --------------------------------------------------------------------------

@dataclass
class _Line:
    text: str
    page: int
    left: float
    top: float
    height: float
    width: float

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def spanning(self) -> bool:
        return self.width >= SPAN_WIDTH_FRAC


@dataclass
class _Unit:
    """One logical line-group: a heading with its wrapped continuation, or a
    run of body prose."""
    lines: List[_Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(ln.text.strip() for ln in self.lines if ln.text.strip())

    @property
    def first_text(self) -> str:
        return self.lines[0].text.strip() if self.lines else ""

    @property
    def page(self) -> int:
        return self.lines[0].page

    @property
    def height(self) -> float:
        return max(ln.height for ln in self.lines)

    @property
    def left(self) -> float:
        return min(ln.left for ln in self.lines)


def _to_lines(blocks: Sequence[TextBlock]) -> List[_Line]:
    out: List[_Line] = []
    for b in blocks:
        box = (b.geometry or {}).get("BoundingBox") or {}
        text = (b.text or "").strip()
        if not text:
            continue
        out.append(
            _Line(
                text=text,
                page=b.page_number,
                left=float(box.get("Left", 0.0)),
                top=float(box.get("Top", 0.0)),
                height=float(box.get("Height", 0.0)) or 0.01,
                width=float(box.get("Width", 0.0)),
            )
        )
    return out


def _assign_columns(lines: Sequence[_Line]) -> List[int]:
    """Cluster lines into columns by left edge.

    Sort the distinct left edges and start a new cluster wherever the gap
    exceeds ``COLUMN_GAP_FRAC``. Indentation inside one column (CO's 0.065 body
    vs 0.078 hanging indent) stays in the same cluster; a genuine column break
    (0.078 -> 0.291) does not.
    """
    if not lines:
        return []
    lefts = sorted({round(ln.left, 4) for ln in lines})
    boundaries: List[float] = []
    for prev, cur in zip(lefts, lefts[1:]):
        if cur - prev > COLUMN_GAP_FRAC:
            boundaries.append((prev + cur) / 2)

    def col_of(left: float) -> int:
        idx = 0
        for b in boundaries:
            if left > b:
                idx += 1
        return idx

    return [col_of(ln.left) for ln in lines]


def _reading_order(lines: Sequence[_Line]) -> List[_Line]:
    """Reconstruct reading order for one page.

    Full-width lines break the page into bands; inside a band, lines are read
    column by column, top to bottom. Without this, a three-column table (CO's
    Indicators / Examples / Suggested Supports spread) interleaves into
    nonsense and every heuristic downstream of it fails for the wrong reason.
    """
    ordered_by_top = sorted(lines, key=lambda ln: (ln.top, ln.left))
    out: List[_Line] = []
    band: List[_Line] = []

    def flush() -> None:
        if not band:
            return
        cols = _assign_columns(band)
        out.extend(
            ln for _, ln in sorted(
                zip(cols, band), key=lambda pair: (pair[0], pair[1].top, pair[1].left)
            )
        )
        band.clear()

    for ln in ordered_by_top:
        if ln.spanning:
            flush()
            out.append(ln)
        else:
            band.append(ln)
    flush()
    return out


def _is_furniture(line: _Line, page_median_height: float) -> bool:
    """Drop page furniture by shape: bare folios, stray glyphs, micro-type."""
    if len(line.text) <= FURNITURE_MAX_CHARS and not line.text.rstrip(".").isalpha():
        return True
    if FOLIO_RE.match(line.text):
        return True
    # Set markedly smaller than the page's body text. Size alone is the test:
    # requiring a margin position first let Colorado's per-page domain tabs
    # through, and 160 of them were emitted as domains.
    return line.height < FURNITURE_SIZE_FRAC * page_median_height


def _group_units(lines: Sequence[_Line]) -> List[_Unit]:
    """Merge wrapped continuation lines into one unit.

    A line continues the previous one when it starts no new heading, sits close
    below it, and shares its column band. Anything else opens a new unit.
    """
    units: List[_Unit] = []
    for ln in lines:
        starts_heading = (
            _heading_signal(ln.text) is not None or _is_age_band_header(ln.text)
        )
        if units and not starts_heading and not _is_age_band_header(units[-1].text):
            prev = units[-1].lines[-1]
            same_page = prev.page == ln.page
            close = 0 <= (ln.top - prev.bottom) <= LINE_GAP_MULTIPLE * prev.height
            aligned = abs(ln.left - prev.left) < CONTINUATION_ALIGN_FRAC
            same_type = (
                prev.height > 0
                and abs(ln.height - prev.height) / prev.height
                <= CONTINUATION_SIZE_TOLERANCE
            )
            if same_page and close and aligned and same_type:
                units[-1].lines.append(ln)
                continue
        units.append(_Unit(lines=[ln]))
    return units


# --------------------------------------------------------------------------
# Heading classification
# --------------------------------------------------------------------------

@dataclass
class _Signal:
    """Why a line reads as a heading, and what that implies about its level."""
    kind: str                     # "label" | "number" | "letter"
    code: str
    remainder: str
    level: Optional[HierarchyLevelEnum]
    depth: int = 0
    age_band: Optional[str] = None


def _heading_signal(text: str) -> Optional[_Signal]:
    """Numbering / label evidence at the start of a line, or None.

    Label evidence is tried first: ``Foundation 1.7`` is a labelled leaf, and
    reading it as a two-segment numbering path would put it at the wrong level.
    """
    stripped = text.strip()
    if not stripped:
        return None

    m = LABEL_HEADING_RE.match(stripped)
    if m:
        word = m.group(1).lower()
        ident = m.group(2) or ""
        remainder = stripped[m.end():].strip()
        if not ident:
            # The identifier can sit on the far side of the separator:
            # California prints "Strand: 1.0 — Motivation to Learn". This is
            # the same "<Label>: <id>" -> "<Label> <id>" fold that
            # detector._canonicalize_code performs for the LLM's output, and
            # it is decided by SHAPE (a numbering path opening the remainder),
            # never by which label word precedes it.
            after = NUMBER_PATH_RE.match(remainder)
            if after and len([x for x in after.group(1).split(".") if x]) >= 2:
                ident = after.group(1)
                remainder = LEADING_SEPARATOR_RE.sub("", remainder[after.end(1):])
        # A bare "Sub-Strand — Curiosity" prints no identifier anywhere, so it
        # supplies no code. Emitting the label word itself would be worse than
        # emitting nothing: it is not an identifier, and it collides across
        # every sibling that carries the same label.
        code = f"{m.group(1)} {ident}".strip() if ident else ""
        return _Signal(
            kind="label",
            code=code,
            remainder=remainder,
            level=LABEL_LEVELS.get(word),
            depth=len(ident.split(".")) if ident else 0,
        )

    m = NUMBER_PATH_RE.match(stripped)
    if m:
        path = m.group(1)
        # An age/column prefix (PK3.) is not a nesting level of its own.
        segments = [s for s in path.split(".") if s]
        # Without a closing terminator, only a multi-segment path is evidence.
        # "A blanket provides comfort" would otherwise open a heading.
        if not m.group(2) and len(segments) < 2:
            return None
        prefixed = bool(segments) and bool(AGE_PREFIX_RE.match(segments[0]))
        core = segments[1:] if prefixed else segments
        depth = max(1, len(core))
        return _Signal(
            kind="number",
            code=path,
            remainder=stripped[m.end():].strip(),
            level=DEPTH_LEVELS.get(depth, HierarchyLevelEnum.INDICATOR),
            depth=depth,
            # An age/column token leading the code IS the item's age band, and
            # it is the only age band this baseline can recover: the other
            # encoding in the corpus is a COLUMN HEADER governing a table
            # column, which needs a header-to-cell mapping rather than a
            # pattern on the item's own text.
            age_band=segments[0] if prefixed else None,
        )

    m = LETTER_ITEM_RE.match(stripped)
    if m:
        return _Signal(
            kind="letter",
            code=m.group(1),
            remainder=stripped[m.end():].strip(),
            level=LETTER_ITEM_LEVEL,
            depth=1,
        )

    return None


def _is_age_band_header(text: str) -> bool:
    """Does this line read as an age-band column header?"""
    t = " ".join(text.split())
    return (
        len(t) <= AGE_BAND_HEADER_MAX_CHARS
        and bool(AGE_BAND_HEADER_RE.match(t))
        and any(c.isalpha() for c in t)
    )


def _is_display_heading(
    unit: _Unit, page_median_height: float, page_p90_height: float
) -> bool:
    """Typographic heading test for a unit carrying no numbering or label.

    Two shapes qualify: an ALL-CAPS line, and a short line set larger than
    both the page's median and its 90th-percentile line height. Both are read
    as a domain, since a document reserves its largest type for its top
    division.

    ⚠️ Both shapes require the line to be at least as tall as the page's body
    text. A heading is never set SMALLER than the text it heads, and without
    that floor every ALL-CAPS navigation tab and running header qualifies.
    """
    text = unit.text
    if len(text) > MAX_TITLE_CHARS or len(text) < 3:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    if unit.height < page_median_height:
        return False
    all_caps = all(c.isupper() for c in letters) and len(letters) >= 3
    larger = unit.height >= max(
        DISPLAY_SIZE_FACTOR * page_median_height, page_p90_height
    )
    short = len(text) <= 90
    return all_caps or (larger and short)


def _split_title(text: str) -> Tuple[str, Optional[str]]:
    """Split a heading unit into its title and any prose that follows it.

    A colon is the one general separator that is not a sentence boundary, so it
    is the only split applied: "Health, Safety and Nutrition: The maintenance
    of…" is a title plus a definition. Without a colon the whole unit is the
    title, because a leaf indicator IS a sentence and splitting it at the first
    period would truncate it.
    """
    text = " ".join(text.split())
    m = COLON_SPLIT_RE.match(text)
    if m:
        title = m.group("title").strip()
        rest = m.group("rest").strip()
        if title and rest:
            return title[:MAX_TITLE_CHARS], rest
    return text[:MAX_TITLE_CHARS], None


def _strip_trailing_label(title: str) -> Tuple[str, Optional[HierarchyLevelEnum]]:
    """Split a trailing structural noun off a title, and read it as evidence.

    "SOCIAL EMOTIONAL DEVELOPMENT STANDARD" -> ("Social Emotional Development",
    strand); "I. Social and Emotional Development Domain" ->
    ("Social and Emotional Development", domain).

    A trailing structural noun names the heading's LEVEL, not the thing, so it
    belongs in neither the title nor nowhere: it is the same evidence a leading
    ``Domain 1:`` gives, printed on the other side.
    """
    m = TRAILING_LABEL_RE.search(title)
    if not m:
        return title, None
    stripped = TRAILING_LABEL_RE.sub("", title).strip()
    if not stripped:
        return title, None
    return stripped, LABEL_LEVELS.get(m.group(1).lower())


def _titlecase_if_shouting(title: str) -> str:
    """An ALL-CAPS heading is a typographic choice; the name underneath is
    title case. Golden titles record the name, so a caps-only comparison would
    fail on presentation rather than on content."""
    letters = [c for c in title if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return " ".join(
            w if (len(w) <= 3 and w.isupper() and not w.isalpha()) else w.capitalize()
            for w in title.split()
        )
    return title


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------

def _page_heights(lines: Sequence[_Line]) -> Tuple[float, float]:
    """(median, 90th percentile) line height for one page.

    Both are needed by ``_is_display_heading``: the median says what body text
    costs on this page, the percentile says what stands out on it.
    """
    heights = sorted(ln.height for ln in lines if ln.height > 0)
    if not heights:
        return 0.01, 0.01
    median = statistics.median(heights)
    p90 = heights[min(len(heights) - 1, int(0.9 * len(heights)))]
    return median, p90


def detect_structure_baseline(
    blocks: List[TextBlock],
    document_s3_key: str = "",
) -> DetectionResult:
    """Detect hierarchy with rules only. Interface-compatible with
    ``els_pipeline.detector.detect_structure``."""
    logger.info("Starting RULE-BASED BASELINE detection for: %s", document_s3_key)
    logger.info("Input: %d text blocks", len(blocks))

    if not blocks:
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            status="error",
            error="No text blocks provided",
        )

    lines = _to_lines(blocks)
    by_page: Dict[int, List[_Line]] = {}
    for ln in lines:
        by_page.setdefault(ln.page, []).append(ln)

    elements: List[DetectedElement] = []

    for page in sorted(by_page):
        page_lines = by_page[page]
        # Two passes over the page's type sizes. The first median includes the
        # furniture and is only good enough to identify it; Colorado's
        # navigation pages are ~50% micro-type, which drags that median well
        # below the real body size. The second is computed over content only
        # and is what the display-heading test compares against.
        rough_median, _ = _page_heights(page_lines)
        kept = [ln for ln in page_lines if not _is_furniture(ln, rough_median)]
        median_h, p90_h = _page_heights(kept)
        units = _group_units(_reading_order(kept))

        pending_description: List[_Unit] = []
        # Age-band column headers seen since the current heading, in reading
        # order. When a heading is followed by these, it is not one element but
        # one PER BAND: California prints a single "Foundation 1.2 Initiative"
        # heading over "Early (3 to 4 ½ Years)" and "Later (4 to 5 1/2 Years)"
        # columns, and the golden set annotates a separate indicator for each.
        # Without this the baseline can never match an age-banded golden entry,
        # since `_match_key` carries the band.
        pending_bands: List[str] = []
        heading_index: Optional[int] = None

        def _apply_bands() -> None:
            """Expand the most recent heading into one element per age band."""
            if heading_index is None or not pending_bands:
                return
            base = elements[heading_index]
            variants = [
                base.model_copy(update={"age_band": band})
                for band in pending_bands
            ]
            elements[heading_index:heading_index + 1] = variants

        for unit in units:
            if _is_age_band_header(unit.text):
                band = " ".join(unit.text.split())
                if band not in pending_bands:
                    pending_bands.append(band)
                continue

            signal = _heading_signal(unit.first_text)
            display = signal is None and _is_display_heading(unit, median_h, p90_h)

            if signal is None and not display:
                pending_description.append(unit)
                continue

            age_band = None
            if signal is not None:
                level = signal.level or HierarchyLevelEnum.INDICATOR
                code = signal.code
                age_band = signal.age_band
                body = signal.remainder
                if len(unit.lines) > 1:
                    body = " ".join(
                        [body] + [ln.text.strip() for ln in unit.lines[1:]]
                    ).strip()
                title, desc = _split_title(body)
                title, trailing_level = _strip_trailing_label(title)
                # Precedence: an explicit label beats positional depth. The
                # numbering says how deep this item sits in ITS OWN list; the
                # noun says what kind of thing it is, and a document that
                # bothers to print "…Domain" has said so outright.
                if trailing_level is not None and signal.kind == "number":
                    level = trailing_level
            else:
                # Typographic prominence outranks a trailing noun: Arizona sets
                # "SOCIAL EMOTIONAL DEVELOPMENT STANDARD" as its largest type
                # on the page, and it is a domain whatever the noun says.
                level = HierarchyLevelEnum.DOMAIN
                code = ""
                raw, _ = _strip_trailing_label(unit.text)
                title, desc = _split_title(raw)
                title = _titlecase_if_shouting(title)

            if not title:
                pending_description.append(unit)
                continue

            # Prose immediately preceding a heading belongs to whatever came
            # before it; prose after it is claimed below by the next iteration.
            if elements and pending_description:
                prev = elements[-1]
                if prev.description is None:
                    prev.description = " ".join(u.text for u in pending_description)
            pending_description = []

            # The bands collected so far belong to the heading they sat under,
            # which is the PREVIOUS one — this unit closes its span.
            _apply_bands()
            pending_bands = []

            elements.append(
                DetectedElement(
                    level=level,
                    code=code or derive_code_from_title(title) or "",
                    title=title,
                    description=desc,
                    confidence=_confidence(signal, display),
                    source_page=page,
                    source_text=unit.text[:1000],
                    age_band=age_band,
                )
            )
            heading_index = len(elements) - 1

        if elements and pending_description and elements[-1].description is None:
            elements[-1].description = " ".join(u.text for u in pending_description)
        _apply_bands()

    level_counts: Dict[str, int] = {}
    for el in elements:
        level_counts[el.level.value] = level_counts.get(el.level.value, 0) + 1
    logger.info("Baseline detection complete: %d elements", len(elements))
    logger.info("Elements by level: %s", level_counts)

    return DetectionResult(
        document_s3_key=document_s3_key,
        elements=elements,
        status="success",
        error=None,
    )


def _confidence(signal: Optional[_Signal], display: bool) -> float:
    """A self-reported score, kept only for interface parity.

    Nothing in the pipeline or the eval gates on ``confidence`` (guardrail 2),
    and a rule's self-assessment carries no information anyway, so these are
    fixed per signal kind rather than tuned.
    """
    if display:
        return 0.60
    if signal is None:
        return 0.50
    return {"label": 0.75, "number": 0.65, "letter": 0.55}.get(signal.kind, 0.50)
