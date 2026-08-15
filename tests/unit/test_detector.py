"""Unit tests for detector post-processing that is deliberately Python, not prompt.

Two document-agnostic concerns are covered here:

* ``_dedup_elements`` — chunk overlap (``DEFAULT_OVERLAP_TOKENS``) re-feeds the
  tail of chunk N into chunk N+1, so a boundary element is emitted twice: once
  TRUNCATED (chunk N ran out of text mid-sentence) and once complete. It can
  also be emitted twice whole but under drifting codes. Both collapse, without
  collapsing same-titled elements that live under DIFFERENT domains.
* ``_block_left`` / ``_serialize_blocks_for_prompt`` — Textract's per-block left
  edge is passed through to the prompt so the MODEL can work out a page's
  column structure. The Python only reads the coordinate and validates its
  range; it deliberately does no clustering of its own.
* ``canonicalize_depth_map_levels`` — a depth's canonical level is a pure
  function of its POSITION in the document's nesting, so it is decided in
  Python rather than left to Pass 1's discretion.
* ``_is_title_grounded`` — whether an element's title actually appears in the
  text it cites is a property of the emitted JSON alone, checkable without
  knowing anything about the document.

One prompt-side contract is asserted here too (``TestDetectionPromptCodeRecovery``).
Rule 4's code-recovery clause has no Python counterpart by design, so the only
thing a test can pin is that the instruction is actually in the prompt the model
receives — and that the guards which keep it off the goldens travel with it.
"""

import json

import pytest

from els_pipeline.models import DetectedElement, HierarchyLevelEnum, TextBlock
from els_pipeline.detector import (
    _block_left,
    _canonicalize_code,
    _dedup_elements,
    _is_code_grounded,
    _is_title_grounded,
    _is_truncated_prefix,
    _resolve_code,
    _serialize_blocks_for_prompt,
    build_detection_prompt,
    canonicalize_depth_map_levels,
    derive_code_from_title,
    parse_llm_response,
)


D = HierarchyLevelEnum.DOMAIN
S = HierarchyLevelEnum.STRAND
SS = HierarchyLevelEnum.SUB_STRAND
I = HierarchyLevelEnum.INDICATOR


def _el(level, code, title, page=1, age_band=None, description="", confidence=0.95):
    return DetectedElement(
        level=level,
        code=code,
        title=title,
        description=description,
        confidence=confidence,
        source_page=page,
        source_text=title,
        age_band=age_band,
    )


def _titles(elements, level):
    return [e.title for e in elements if e.level == level]


def _el_src(level, code, title, source_text, age_band=None, confidence=0.95):
    """Like _el, but with source_text decoupled from title — the grounding
    check is precisely about the two disagreeing."""
    return DetectedElement(
        level=level, code=code, title=title, description="",
        confidence=confidence, source_page=1, source_text=source_text,
        age_band=age_band,
    )


class TestAgeBandDriftReconciliation:
    """One column read two ways across chunks folds back to one label.

    Chunk N reads a header as "PK3", chunk N+1 as "PK3 Outcome". Because
    ``_dedup_elements`` keys identity on age_band, the two spellings split one
    column in two and the overlap copies never collapse — which downstream
    becomes duplicate standards colliding on standard_id.
    """

    def test_drifted_column_folds_and_overlap_copies_collapse(self):
        els = [
            _el(I, "PK3.I.B.1.b", "Child takes care of materials", page=5, age_band="PK3"),
            _el(I, "PK3.I.B.1.b", "Child takes care of materials", page=5,
                age_band="PK3 Outcome"),
        ]
        out = _dedup_elements(els)
        assert len(out) == 1
        assert out[0].age_band == "PK3"

    def test_fold_applies_document_wide_once_evidenced(self):
        # Evidence comes from the B.1.b pair; the B.2.c element carries the
        # drifted label with no twin of its own and must still be folded.
        els = [
            _el(I, "PK3.I.B.1.b", "Takes care of materials", page=5, age_band="PK3"),
            _el(I, "PK3.I.B.1.b", "Takes care of materials", page=5, age_band="PK3 Outcome"),
            _el(I, "PK3.I.B.2.c", "Manages intensity of emotions", page=6,
                age_band="PK3 Outcome"),
        ]
        out = _dedup_elements(els)
        assert {e.age_band for e in out} == {"PK3"}

    def test_distinct_bands_sharing_a_prefix_are_not_merged(self):
        # "Age 3" is a token-prefix of "Age 3 to 4", but they sit on DIFFERENT
        # elements — no same-element evidence, so this is two real bands.
        els = [
            _el(I, "1.1", "Walks unaided", page=2, age_band="Age 3"),
            _el(I, "1.2", "Runs and climbs", page=2, age_band="Age 3 to 4"),
        ]
        out = _dedup_elements(els)
        assert {e.age_band for e in out} == {"Age 3", "Age 3 to 4"}
        assert len(out) == 2

    def test_unrelated_bands_are_untouched(self):
        # CA's real bands: neither prefix-related nor foldable.
        for bands in (
            ("Early (3 to 4 ½ Years)", "Later (4 to 5 ½ Years)"),
            ("Discovering", "Developing"),
            ("Discovering", "Broadening"),
        ):
            els = [
                _el(I, "Foundation 1.1", "Understanding Words", page=3, age_band=bands[0]),
                _el(I, "Foundation 1.1", "Understanding Words", page=3, age_band=bands[1]),
            ]
            out = _dedup_elements(els)
            assert {e.age_band for e in out} == set(bands), bands
            assert len(out) == 2

    def test_single_band_document_is_a_noop(self):
        els = [_el(I, "1.1", "Only one band", page=1, age_band="PK4")]
        assert [e.age_band for e in _dedup_elements(els)] == ["PK4"]

    def test_elements_without_an_age_band_are_unaffected(self):
        els = [
            _el(D, "I", "Social and Emotional Development", page=1),
            _el(I, "PK3.I.A.1", "Controls own body", page=2, age_band="PK3"),
            _el(I, "PK3.I.A.1", "Controls own body", page=2, age_band="PK3 Outcome"),
        ]
        out = _dedup_elements(els)
        assert [(e.level, e.age_band) for e in out] == [(D, None), (I, "PK3")]


class TestCanonicalizeCode:
    """`<Label>: <id>` folds to `<Label> <id>`; everything else is untouched.

    The LLM carries the heading's colon into the code inconsistently — CA emits
    "Strand: 1.0" six times and "Strand 2.0" once — which splits one construct
    into two codes that no longer reconcile across chunks.
    """

    @pytest.mark.parametrize("raw,expected", [
        ("Strand: 1.0", "Strand 1.0"),
        ("Strand:1.0", "Strand 1.0"),          # no space after the colon
        ("Strand :  1.0", "Strand 1.0"),       # space before, doubled after
        ("Concept: 2", "Concept 2"),
        ("Sub-Strand: V", "Sub-Strand V"),     # hyphenated label word
        ("Goal: A", "Goal A"),
    ])
    def test_colon_separator_is_dropped(self, raw, expected):
        assert _canonicalize_code(raw) == expected

    @pytest.mark.parametrize("code", [
        "Strand 2.0",        # already canonical
        "Foundation 1.2",
        "PK3.I.A.2",         # dotted document code
        "1.0-V",             # hyphen is meaningful, not a label separator
        "A-1",
        "VOCA", "CAP", "SED",
        "a", "b",            # lettered leaf indicators
        "1.1", "4.3",
    ])
    def test_codes_without_the_label_shape_are_untouched(self, code):
        assert _canonicalize_code(code) == code

    def test_leading_digit_is_not_a_label(self):
        # "1.0: V" must not be read as label "1.0" — the shape requires the
        # label to start with a letter.
        assert _canonicalize_code("1.0: V") == "1.0: V"

    def test_non_string_passes_through(self):
        assert _canonicalize_code(None) is None

    def test_applied_when_building_an_element(self):
        payload = json.dumps([
            {"level": "strand", "code": "Strand: 1.0",
             "title": "Listening and Speaking", "description": "",
             "confidence": 0.97, "source_page": 1,
             "source_text": "Strand: 1.0 — Listening and Speaking"},
        ])
        out = parse_llm_response(payload, [])
        assert [e.code for e in out] == ["Strand 1.0"]

    def test_two_spellings_of_one_strand_collapse_to_one_element(self):
        # The point of the canonicalization: the drifted pair must reconcile.
        payload = json.dumps([
            {"level": "strand", "code": "Strand: 2.0", "title": "Foundational Literacy Skills",
             "description": "", "confidence": 0.97, "source_page": 3,
             "source_text": "Strand: 2.0 — Foundational Literacy Skills"},
            {"level": "strand", "code": "Strand 2.0", "title": "Foundational Literacy Skills",
             "description": "", "confidence": 0.96, "source_page": 3,
             "source_text": "Strand 2.0 Foundational Literacy Skills"},
        ])
        parsed = parse_llm_response(payload, [])
        assert {e.code for e in parsed} == {"Strand 2.0"}
        assert len(_dedup_elements(parsed)) == 1


class TestTitleGrounding:
    """A heading's title must appear in the text it cites as its source.

    Guards the back-formed-parent failure: a chunk opening mid-section shows
    the LLM child codes naming their ancestors, and the model reconstructs an
    ancestor whose heading is not on the page — citing the child's line as its
    source_text.
    """

    def test_heading_transcribed_from_its_own_line_is_grounded(self):
        assert _is_title_grounded(
            _el_src(SS, "1", "Behavior Control", "1. Behavior Control")
        )

    def test_back_formed_parent_citing_a_child_line_is_rejected(self):
        # The observed TX failure: sub_strand "1 / Behavior Control" invented
        # from the ".1." inside an indicator's code.
        assert not _is_title_grounded(
            _el_src(
                SS, "1", "Behavior Control",
                "PK3.I.B.1.b Child takes care of and manages classroom materials "
                "with adult assistance.",
                confidence=0.85,
            )
        )

    def test_wrapped_heading_is_grounded_across_the_line_break(self):
        assert _is_title_grounded(
            _el_src(S, "A", "Self-Concept and Self-Regulation",
                    "A. Self-Concept and\nSelf-Regulation")
        )

    def test_all_caps_running_header_normalized_to_title_case_is_grounded(self):
        # Prompt rule 4 folds a repeated ALL-CAPS page header back to the bare
        # title; the comparison is case-insensitive so that stays grounded.
        assert _is_title_grounded(
            _el_src(D, "SED", "Social Emotional Development",
                    "SOCIAL EMOTIONAL DEVELOPMENT STANDARD")
        )

    def test_punctuation_and_glyph_drift_does_not_reject(self):
        assert _is_title_grounded(
            _el_src(S, "1.0", "Listening and Speaking",
                    "Strand: 1.0 — “Listening and Speaking”")
        )

    def test_indicators_are_exempt_for_age_band_columns(self):
        # Rule 3 gives every column indicator the row's shared header as its
        # title while source_text holds only that column's cell. Correct
        # output, and it must not be dropped.
        assert _is_title_grounded(
            _el_src(I, "Foundation 1.1", "Curiosity and Interest",
                    "Later (4 to 5 ½ Years)\nExpress interest in a broader range "
                    "of familiar and new experiences.",
                    age_band="Later (4 to 5 ½ Years)")
        )

    def test_empty_title_asserts_nothing(self):
        assert _is_title_grounded(_el_src(SS, "1", "", "anything at all"))

    def test_parse_llm_response_drops_the_ungrounded_heading_only(self):
        payload = json.dumps([
            {"level": "sub_strand", "code": "2", "title": "Emotional Control",
             "description": "", "confidence": 0.97, "source_page": 5,
             "source_text": "2. Emotional Control"},
            {"level": "sub_strand", "code": "1", "title": "Behavior Control",
             "description": "", "confidence": 0.85, "source_page": 5,
             "source_text": "PK3.I.B.1.b Child takes care of and manages "
                            "classroom materials with adult assistance."},
            {"level": "indicator", "code": "PK3.I.B.2.c", "title": "Child manages "
             "intensity of emotions with adult assistance",
             "description": "", "confidence": 0.95, "source_page": 5,
             "source_text": "PK3.I.B.2.c Child manages intensity of emotions "
                            "with adult assistance."},
        ])
        out = parse_llm_response(payload, [])
        assert [(e.level, e.code) for e in out] == [
            (SS, "2"),
            (I, "PK3.I.B.2.c"),
        ]


class TestTruncatedPrefix:
    """The predicate behind prefix dominance, in isolation."""

    def test_word_boundary_prefix_is_truncation(self):
        assert _is_truncated_prefix(
            "child is familiar with basic feeling",
            "child is familiar with basic feeling words (e.g., happy, sad)",
        )

    def test_trailing_punctuation_still_counts_as_boundary(self):
        # CO's truncated twin ends on a comma mid-list.
        assert _is_truncated_prefix(
            "recognize self as a unique individual having own abilities,",
            "recognize self as a unique individual having own abilities, "
            "characteristics, and preferences",
        )

    def test_mid_word_cut_is_not_a_truncation(self):
        # "feel" continues into "feeling" — the boundary test rejects it.
        assert not _is_truncated_prefix(
            "child is familiar with basic feel",
            "child is familiar with basic feeling words",
        )

    def test_short_title_never_dominates(self):
        # "Physical Dev" is a prefix of "Physical Development" but far too
        # short to risk merging two label-like titles.
        assert not _is_truncated_prefix("physical dev", "physical development")

    def test_identical_titles_are_not_a_prefix_pair(self):
        assert not _is_truncated_prefix("a" * 20, "a" * 20)


class TestDedupTruncatedTwins:
    def test_truncated_twin_collapses_into_complete_form(self):
        """TX PK3.I.B.2.b was emitted truncated at the chunk boundary and whole
        in the next chunk. One indicator must survive, with the full title."""
        full = "Child is familiar with basic feeling words (e.g., happy, sad, mad, scared)"
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(I, "PK3.I.B.2.b", "Child is familiar with basic feeling",
                page=6, age_band="PK3"),
            _el(I, "PK3.I.B.2.b", full, page=6, age_band="PK3"),
        ]
        out = _dedup_elements(elements)
        assert _titles(out, I) == [full]

    def test_truncation_merge_keeps_the_richer_description(self):
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(I, "1.", "Recognize self as a unique individual having own",
                page=7, description="short"),
            _el(I, "1.",
                "Recognize self as a unique individual having own abilities, "
                "characteristics, and preferences",
                page=7, description="a much longer and complete description"),
        ]
        out = _dedup_elements(elements)
        indicators = [e for e in out if e.level == I]
        assert len(indicators) == 1
        assert indicators[0].description == "a much longer and complete description"

    def test_truncated_twin_keeps_the_earliest_document_position(self):
        full = "Child uses verbal and nonverbal communication to communicate feelings"
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(I, "PK4.I.B.2.b", "Child uses verbal and nonverbal",
                page=6, age_band="PK4"),
            _el(I, "PK4.I.B.2.a", "Child recognizes emotions", page=6, age_band="PK4"),
            _el(I, "PK4.I.B.2.b", full, page=6, age_band="PK4"),
        ]
        out = _dedup_elements(elements)
        assert _titles(out, I) == [full, "Child recognizes emotions"]

    def test_different_age_bands_never_merge(self):
        """Side-by-side age columns are distinct indicators even when one
        column's prose is a prefix of the other's."""
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(I, "I.B.2.b", "Child is familiar with basic feeling words",
                page=6, age_band="PK3"),
            _el(I, "I.B.2.b",
                "Child is familiar with basic feeling words and their causes",
                page=6, age_band="PK4"),
        ]
        out = _dedup_elements(elements)
        assert len(_titles(out, I)) == 2

    def test_different_codes_never_merge_by_prefix(self):
        """Two genuinely distinct siblings can share a long title prefix; their
        codes differ, so prefix dominance must not touch them."""
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(I, "I.B.1", "Child demonstrates self awareness", page=6),
            _el(I, "I.B.2", "Child demonstrates self awareness and self control",
                page=6),
        ]
        out = _dedup_elements(elements)
        assert len(_titles(out, I)) == 2


class TestDedupDomainScoping:
    def test_same_title_under_two_domains_is_not_collapsed(self):
        """CA's ELD and FLD domains each own a "Listening and Speaking" strand
        and a "Vocabulary" sub_strand. These are four distinct elements."""
        elements = [
            _el(D, "FLD", "Foundational Language Development"),
            _el(S, "FLD.1.0", "Listening and Speaking"),
            _el(SS, "FLD.1.0.VOCA", "Vocabulary"),
            _el(D, "ELD", "English Language Development"),
            _el(S, "ELD.1.0", "Listening and Speaking"),
            _el(SS, "ELD.1.0.VOCA", "Vocabulary"),
        ]
        out = _dedup_elements(elements)
        assert len(_titles(out, S)) == 2
        assert len(_titles(out, SS)) == 2
        assert len(_titles(out, D)) == 2

    def test_prefix_dominance_does_not_reach_across_domains(self):
        elements = [
            _el(D, "FLD", "Foundational Language Development"),
            _el(I, "1.1", "Recognize and produce the sounds of spoken language",
                page=2),
            _el(D, "ELD", "English Language Development"),
            _el(I, "1.1",
                "Recognize and produce the sounds of spoken language in English",
                page=9),
        ]
        out = _dedup_elements(elements)
        assert len(_titles(out, I)) == 2


class TestDedupCodeReconciliation:
    def test_same_domain_under_two_codes_collapses_to_one(self):
        """TX emitted "Social and Emotional Development" as SED on page 2 and
        as I on page 5. Codes reconcile, then the duplicate collapses."""
        elements = [
            _el(D, "SED", "Social and Emotional Development", page=2),
            _el(I, "SED.1", "Child expresses needs", page=2),
            _el(D, "I", "Social and Emotional Development", page=5),
        ]
        out = _dedup_elements(elements)
        domains = [e for e in out if e.level == D]
        assert len(domains) == 1
        # Every surviving instance agrees on one code, whichever the shared
        # reconciliation machinery picks.
        assert domains[0].code in {"SED", "I"}

    def test_same_sub_strand_under_two_codes_reconciles_to_one_code(self):
        """TX "Behavior Control" arrived as "1" then "1.b".

        Asserts CODE RECONCILIATION, not row collapse. These two rows sit on
        different pages, and cross-page collapse is deliberately no longer
        performed: a document that names an element on a contents page AND
        again as its own section header is the same shape as this test, and
        collapsing those relocated AZ's seven sub_strand headers to the
        contents page, orphaning 37 indicators and destroying 13 standard_ids.
        Reconciling the code is the behavior the pipeline actually needs (and
        the part CLAUDE.md whitelists as cross-chunk reconciliation); a
        surviving duplicate row is cosmetic and measurably harmless — the
        page-keyed 07-17 run carried both rows and still produced 25/25
        distinct TX standard_ids.
        """
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(SS, "1", "Behavior Control", page=4),
            _el(SS, "1.b", "Behavior Control", page=5),
        ]
        out = _dedup_elements(elements)
        sub_strands = [e for e in out if e.level == SS]
        assert {e.code for e in sub_strands} == {"1"}

    def test_case_variant_running_header_reconciles_to_one_code(self):
        """AZ repeats a strand heading as an ALL-CAPS running page header.

        Same rationale as above. Note TITLE normalization ("EMERGENT LITERACY"
        back to "Emergent Literacy") is the detector PROMPT's job per CLAUDE.md,
        not this dedup pass's — asserting it here tests the wrong layer.
        """
        elements = [
            _el(D, "LL", "Language and Literacy"),
            _el(S, "Strand 2", "Emergent Literacy", page=4),
            _el(S, "STRAND 2", "EMERGENT LITERACY", page=12),
        ]
        out = _dedup_elements(elements)
        strands = [e for e in out if e.level == S]
        assert len({e.code for e in strands}) == 1

    def test_contents_page_stub_does_not_absorb_its_body_header(self):
        """Regression pin for the AZ 13-standard_id loss.

        A contents page lists every Concept by name; each Concept then appears
        again as its own section header, later, immediately above its own
        indicators. These must NOT collapse — the survivor would inherit the
        contents-page POSITION, leaving the real indicators with no preceding
        parent. Keyed on source_page precisely so this cannot happen.
        """
        elements = [
            _el(D, "LL", "Language and Literacy", page=4),
            _el(SS, "Concept 1", "Concepts of Print", page=4),  # contents stub
            _el(SS, "Concept 1", "Concepts of Print", page=9),  # real header
            _el(I, "a", "Child points to the title", page=9),
        ]
        out = _dedup_elements(elements)
        sub_strands = [e for e in out if e.level == SS]
        assert len(sub_strands) == 2
        # The body header must still precede its own indicator.
        titles = [e.title for e in out]
        assert titles.index("Concepts of Print") < titles.index(
            "Child points to the title"
        )

    def test_empty_input_is_returned_unchanged(self):
        assert _dedup_elements([]) == []

    def test_distinct_elements_are_all_preserved_in_order(self):
        elements = [
            _el(D, "I", "Social and Emotional Development"),
            _el(SS, "1", "Behavior Control"),
            _el(I, "1.a", "Child follows classroom rules"),
            _el(I, "1.b", "Child manages transitions"),
        ]
        out = _dedup_elements(elements)
        assert [e.title for e in out] == [e.title for e in elements]


# ---------------------------------------------------------------------------
# Column geometry
# ---------------------------------------------------------------------------


def _block(text, page, left, width=0.2, top=0.0):
    return TextBlock(
        text=text,
        page_number=page,
        block_type="LINE",
        confidence=0.99,
        geometry={"BoundingBox": {
            "Left": left, "Top": top, "Width": width, "Height": 0.02,
        }},
    )


class TestBlockLeft:
    """`_block_left` is deliberately thin: read the coordinate, validate its
    range, hand it to the prompt. Grouping lines into columns is the MODEL's
    job — clustering them here would decide the document's layout on the
    model's behalf. See CLAUDE.md on keeping detector.py LLM-driven."""

    def test_reads_normalized_left_edge(self):
        assert _block_left(_block("a", 1, 0.088)) == 0.088

    def test_missing_geometry_returns_none(self):
        block = TextBlock(text="a", page_number=1, block_type="LINE",
                          confidence=0.9, geometry={})
        assert _block_left(block) is None

    def test_non_numeric_left_returns_none(self):
        block = TextBlock(text="a", page_number=1, block_type="LINE", confidence=0.9,
                          geometry={"BoundingBox": {"Left": "x", "Top": 0,
                                                    "Width": 0.2, "Height": 0.1}})
        assert _block_left(block) is None

    def test_out_of_range_left_returns_none(self):
        block = TextBlock(text="a", page_number=1, block_type="LINE", confidence=0.9,
                          geometry={"BoundingBox": {"Left": 1.4, "Top": 0,
                                                    "Width": 0.2, "Height": 0.1}})
        assert _block_left(block) is None


class TestPromptSerialization:
    def test_coordinate_tag_is_emitted_and_document_order_preserved(self):
        blocks = []
        for row in range(6):
            blocks.append(_block(f"left{row}", 3, 0.088, top=row / 10))
            blocks.append(_block(f"right{row}", 3, 0.643, top=row / 10))
        lines = _serialize_blocks_for_prompt(blocks).splitlines()
        assert lines[0] == "[Page 3 | x=0.09] left0"
        assert lines[1] == "[Page 3 | x=0.64] right0"
        # Document order, not column order — chunk_text_blocks slices this same
        # sequence, so re-sorting would split a column's head from its tail.
        assert [l.split("] ")[1] for l in lines] == [b.text for b in blocks]

    def test_interleaved_columns_stay_distinguishable_by_coordinate(self):
        """CA page 12: three proficiency columns arrive interleaved line by
        line. The model must be able to tell them apart from x alone."""
        blocks = []
        for row in range(4):
            for left in (0.088, 0.366, 0.643):
                blocks.append(_block(f"r{row}c{left}", 12, left, top=row / 10))
        lines = _serialize_blocks_for_prompt(blocks).splitlines()
        assert len({l.split("] ")[0] for l in lines}) == 3

    def test_block_without_geometry_falls_back_to_page_only(self):
        blocks = [
            TextBlock(text="scanned", page_number=4, block_type="LINE",
                      confidence=0.9, geometry={}),
            _block("clean", 4, 0.09),
        ]
        lines = _serialize_blocks_for_prompt(blocks).splitlines()
        assert lines == ["[Page 4] scanned", "[Page 4 | x=0.09] clean"]

    def test_empty_input(self):
        assert _serialize_blocks_for_prompt([]) == ""


def _dm(*levels, labels=None):
    return {
        "doc_depths": [
            {
                "depth": i + 1,
                "canonical_level": lvl,
                "label_in_doc": (labels or {}).get(i + 1, "Level"),
            }
            for i, lvl in enumerate(levels)
        ],
        "notes": "",
    }


def _levels(depth_map):
    return [d["canonical_level"] for d in depth_map["doc_depths"]]


class TestCanonicalizeDepthMapLevels:
    def test_four_level_document_is_unchanged(self):
        dm = _dm("domain", "strand", "sub_strand", "indicator")
        assert _levels(canonicalize_depth_map_levels(dm)) == [
            "domain", "strand", "sub_strand", "indicator",
        ]

    def test_three_level_middle_is_a_strand_not_a_sub_strand(self):
        """CO: domain > section > indicator. The one middle level is a STRAND;
        the goldens and the parser's null-sub_strand contract depend on it."""
        dm = _dm("domain", "sub_strand", "indicator")
        assert _levels(canonicalize_depth_map_levels(dm)) == [
            "domain", "strand", "indicator",
        ]

    def test_two_level_document(self):
        dm = _dm("domain", "strand")
        assert _levels(canonicalize_depth_map_levels(dm)) == ["domain", "indicator"]

    def test_five_levels_fill_the_middle_with_sub_strand(self):
        dm = _dm("domain", "domain", "domain", "domain", "domain")
        assert _levels(canonicalize_depth_map_levels(dm)) == [
            "domain", "strand", "sub_strand", "sub_strand", "indicator",
        ]

    def test_document_label_words_never_decide_the_level(self):
        """A doc that CALLS its middle level "Sub-Strand" still maps it to
        strand when it sits directly under domain."""
        dm = _dm(
            "domain", "sub_strand", "indicator",
            labels={1: "Domain", 2: "Sub-Strand", 3: "Foundation"},
        )
        canonicalize_depth_map_levels(dm)
        assert _levels(dm) == ["domain", "strand", "indicator"]
        # The label the document uses is preserved as metadata, untouched.
        assert dm["doc_depths"][1]["label_in_doc"] == "Sub-Strand"

    def test_out_of_order_depths_are_ordered_before_mapping(self):
        dm = _dm("indicator", "domain", "strand")
        dm["doc_depths"] = list(reversed(dm["doc_depths"]))
        canonicalize_depth_map_levels(dm)
        by_depth = {d["depth"]: d["canonical_level"] for d in dm["doc_depths"]}
        assert by_depth == {1: "domain", 2: "strand", 3: "indicator"}

    def test_degenerate_maps_are_left_alone(self):
        for dm in ({}, {"doc_depths": []}, _dm("domain"), {"doc_depths": "nope"}):
            assert canonicalize_depth_map_levels(dm) is dm
        assert _levels(canonicalize_depth_map_levels(_dm("domain"))) == ["domain"]


class TestDeriveCodeFromTitle:
    """Prompt rule 4's abbreviation procedure, executed deterministically.

    The rule is a string algorithm; the LLM samples it. Three temperature-0
    detector runs over one frozen Kentucky extraction gave 11 of 44 elements a
    different code on at least one run, so the same standard would reach Aurora
    under different primary keys depending on which run wrote it.
    """

    @pytest.mark.parametrize("title,expected", [
        # (c) several content words -> initials, capped at 5
        ("Approaches to Learning", "AL"),
        ("Physical Development", "PD"),
        ("Concepts About Print", "CP"),
        ("Language and Early Literacy", "LEL"),
        ("Engages in an activity for a sustained period of time", "EASPT"),
        # (c) exactly one content word -> its first four letters
        ("Vocabulary", "VOCA"),
        ("Initiative", "INIT"),
        # (a) a hyphenated compound is ONE word
        ("Persists with self-selected activities until completed", "PSAUC"),
        # (a) a slash splits
        ("Health/Mental Wellness", "HMW"),
        ("Takes care of personal health/safety needs with adult support as needed", "TCPHS"),
        # (b) the symbol & is a connector
        ("Social & Emotional Development", "SED"),
    ])
    def test_rule_four_examples(self, title, expected):
        assert derive_code_from_title(title) == expected

    def test_trailing_punctuation_is_ignored(self):
        assert derive_code_from_title("Follows simple directions.") == "FSD"

    def test_connectors_are_matched_case_insensitively(self):
        assert derive_code_from_title("Uses Words And Signs") == "UWS"

    def test_all_connector_title_keeps_its_words(self):
        # Rule 4(d): dropping connectors would leave nothing, so (c) is applied
        # to the words as they are rather than returning an empty code.
        assert derive_code_from_title("Of the and") == "OTA"

    @pytest.mark.parametrize("title", ["", "   ", None, 42])
    def test_degenerate_titles_yield_no_code(self, title):
        assert derive_code_from_title(title) is None


class TestCodeGrounding:
    """Which branch of rule 4 produced this code — the document, or the model?

    A code the document prints is read off the page and so appears in the
    element's own ``source_text``; an invented abbreviation is derived from the
    title and appears nowhere in it. Only the invented kind is recomputed.
    """

    @pytest.mark.parametrize("code,source_text", [
        ("Benchmark 1.1", "Benchmark 1.1: Maintains focus and sustains attention."),
        ("Standard 2", "Language and Early Literacy Standard 2: Demonstrates the knowledge"),
        ("I.A.2", "I.A.2 Child shows initiative in trying new activities"),
        ("PK3.I.A.2", "PK3.I.A.2 Child uses language"),
        ("1.0", "1.0 Listening and Speaking"),
        ("a", "a. Demonstrates self-confidence."),
        # The canonicalized spelling must still match the page's original one —
        # `_canonicalize_code` folds "Strand: 1.0" to "Strand 1.0" first.
        ("Strand 1.0", "Strand: 1.0 — Listening and Speaking"),
    ])
    def test_document_codes_are_grounded(self, code, source_text):
        assert _is_code_grounded(code, source_text) is True

    @pytest.mark.parametrize("code,source_text", [
        ("EASPT", "Engages in an activity for a sustained period of time."),
        ("AL", "Approaches to Learning"),
        ("VOCA", "Vocabulary"),
        # Case-sensitivity matters: the ordinary English word "as" must not
        # ground a derived code "AS".
        ("AS", "Uses gestures as needed"),
        # Nor may a short code match inside a longer word.
        ("CP", "Concepts About Print"),
    ])
    def test_invented_codes_are_not_grounded(self, code, source_text):
        assert _is_code_grounded(code, source_text) is False

    @pytest.mark.parametrize("code,source_text", [
        (None, "text"), ("", "text"), ("  ", "text"), ("AL", None), ("AL", ""),
    ])
    def test_degenerate_input_is_not_grounded(self, code, source_text):
        assert _is_code_grounded(code, source_text) is False


class TestResolveCode:
    """`_resolve_code` recomputes ONLY the codes the model invented."""

    def test_document_code_is_never_overwritten(self):
        # Even though the title would derive "MFSA", the document printed a code.
        assert _resolve_code(
            "Benchmark 1.1", "Maintains focus and sustains attention.",
            "Benchmark 1.1: Maintains focus and sustains attention.",
        ) == "Benchmark 1.1"

    def test_invented_code_is_recomputed(self):
        # The connector "and" must not reach the code — the model kept it.
        assert _resolve_code(
            "MFAAA", "Maintains focus and attention on activities despite distractions and interruptions",
            "Maintains focus and attention on activities despite distractions and interruptions.",
        ) == "MFAAD"

    def test_a_correct_invented_code_is_left_as_is(self):
        assert _resolve_code(
            "EASPT", "Engages in an activity for a sustained period of time",
            "Engages in an activity for a sustained period of time.",
        ) == "EASPT"

    def test_drifted_spellings_of_one_title_converge(self):
        # The point of the pass: three runs, three codes, one answer.
        title = "Experiments with combining objects and materials in new and imaginative ways"
        src = title + "."
        assert {_resolve_code(c, title, src) for c in ("ECOM", "EWCOM", "ECOMN")} == {"ECOMN"}

    def test_untitled_element_keeps_its_code(self):
        assert _resolve_code("XYZ", "", "no code here") == "XYZ"

    def test_applied_when_building_an_element(self):
        payload = json.dumps([
            {"level": "indicator", "code": "MFAAA",
             "title": "Maintains focus and attention on activities despite distractions and interruptions",
             "description": "", "confidence": 0.95, "source_page": 2,
             "source_text": "Maintains focus and attention on activities despite distractions and interruptions."},
        ])
        assert [e.code for e in parse_llm_response(payload, [])] == ["MFAAD"]

    @pytest.mark.parametrize("code,source_text", [
        # Rule 4's OTHER branch: a lettered leaf's code is just its list letter.
        # The model sometimes drops the "a. " prefix from source_text, so
        # grounding alone would read this as invented (observed on AZ).
        ("a", "Demonstrates self-confidence."),
        ("b", "Shows pride in accomplishments."),
        # Positional document codes whose source_text got truncated.
        ("1.0", "Listening and Speaking"),
        ("PK3.I.A.2", "Child uses language"),
        ("Benchmark 1.1", "Maintains focus and sustains attention."),
    ])
    def test_non_abbreviation_shapes_are_never_recomputed(self, code, source_text):
        assert _resolve_code(code, "Demonstrates self-confidence", source_text) == code


class TestDetectionPromptCodeRecovery:
    """Rule 4's code-recovery clause is prompt-only — assert it is really there.
    """

    @staticmethod
    def _prompt() -> str:
        return build_detection_prompt([
            TextBlock(text="Science", page_number=1, block_type="LINE",
                      confidence=0.99, geometry={}),
        ])

    def test_names_all_three_places_a_code_can_live(self):
        prompt = self._prompt()
        assert "ON THE HEADING LINE" in prompt
        assert "IN A CAPTION BESIDE THE HEADING" in prompt
        assert "FROM ITS DESCENDANTS' CODES" in prompt

    def test_states_the_ancestor_prefix_principle(self):
        assert (
            "An ancestor's code is the COMMON PREFIX of its descendants' document codes"
            in self._prompt()
        )

    def test_recovered_code_outranks_a_derived_abbreviation(self):
        prompt = self._prompt()
        # Precedence must be explicit in both directions: recovery wins, and
        # the abbreviation branch is reachable only once recovery has failed.
        assert "ALWAYS beats one you would derive from the title" in prompt
        assert "ONLY when all three come up empty" in prompt

    def test_prefix_is_peeled_one_segment_per_level(self):
        # A raw common prefix over-reaches when a chunk shows only one group
        # under a heading; peeling per level is what keeps a domain at "CD".
        prompt = self._prompt()
        assert "Peel exactly ONE segment per level as you move UP" in prompt
        assert "consumes NO segment" in prompt

    def test_carries_the_guards_that_keep_it_off_the_goldens(self):
        prompt = self._prompt()
        # More than one segment (CO's "1"/"6", AZ's "a"/"b" carry no ancestor).
        assert "MORE THAN ONE dot-separated segment" in prompt
        # Two agreeing descendants (a lone "PK3.I.A.2" must not donate a prefix).
        assert "At least TWO descendants must agree on the prefix" in prompt
        assert "Only WHOLE segments count" in prompt
        # A labelled id belongs to the descendant's own level — this is what
        # stops CA's "Foundation 1.7" from coding its sub_strand "Foundation 1".
        assert "structural LABEL word" in prompt
        assert "is NOT a namespace path" in prompt

    def test_requires_the_evidence_line_in_source_text(self):
        # Load-bearing: a recovered short code ("T") has the abbreviation
        # branch's shape, so `_resolve_code` recomputes it to "TECH" unless it
        # is grounded in the element's own source_text.
        prompt = self._prompt()
        assert "cite the line it came from in `source_text` IN ADDITION to the heading line" in prompt

    def test_does_not_license_emitting_an_unseen_ancestor(self):
        # Rule 1 still owns WHETHER an element is emitted; this clause only
        # decides WHICH code an element already being emitted gets.
        assert "It NEVER licenses emitting an element you cannot see" in self._prompt()

    def test_mentions_no_state_specific_token(self):
        """The clause must be stated as document structure, not as Nevada.

        Its examples are placeholders ("CD.WM", "CD.AT"); NV's own tokens must
        never appear, or the prompt has been overfitted to the canary state the
        change is supposed to generalize to.
        """
        prompt = self._prompt()
        for token in ("SS.ID", "SS.CI", "SS.GH", "S.EO", "S.SI", "T.TT", "T.CT", "Nevada"):
            assert token not in prompt
