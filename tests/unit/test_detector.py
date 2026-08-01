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
"""

import json

import pytest

from els_pipeline.models import DetectedElement, HierarchyLevelEnum, TextBlock
from els_pipeline.detector import (
    _block_left,
    _canonicalize_code,
    _dedup_elements,
    _is_title_grounded,
    _is_truncated_prefix,
    _serialize_blocks_for_prompt,
    canonicalize_depth_map_levels,
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
