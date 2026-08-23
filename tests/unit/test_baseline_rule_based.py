"""Unit tests for the arXiv paper's rule-based baseline (Task 4).

The baseline is a throwaway that lives only in ``evaluation/baselines/``, but
its numbers go into a published table, so the behaviours that are easy to break
silently are pinned here. Two kinds of test:

  1. **Mechanism** — the layout and heading rules do what the module docstring
     claims, on synthetic pages rather than on any state's real text.
  2. **Anti-overfit guards** — the properties that keep the baseline honest.
     ``test_no_state_name_appears_in_the_source`` is the important one: the
     whole comparison is worthless if the baseline was tuned per document.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from els_pipeline.models import HierarchyLevelEnum, TextBlock
from evaluation.baselines import rule_based
from evaluation.baselines.rule_based import (
    LABEL_LEVELS,
    TRAILING_LABEL_WORDS,
    _heading_signal,
    _is_age_band_header,
    _reading_order,
    _strip_trailing_label,
    _to_lines,
    detect_structure_baseline,
)


def _block(text: str, page: int = 1, left: float = 0.1, top: float = 0.1,
           height: float = 0.02, width: float = 0.3) -> TextBlock:
    return TextBlock(
        text=text, page_number=page, block_type="LINE", confidence=1.0,
        geometry={"BoundingBox": {"Left": left, "Top": top,
                                  "Height": height, "Width": width}},
    )


# --------------------------------------------------------------------------
# Heading signals
# --------------------------------------------------------------------------

class TestHeadingSignal:
    def test_label_with_identifier_becomes_the_code(self):
        sig = _heading_signal("Strand 1: Self-Awareness and Emotional Skills")
        assert sig is not None
        assert sig.code == "Strand 1"
        assert sig.remainder == "Self-Awareness and Emotional Skills"
        assert sig.level is HierarchyLevelEnum.STRAND

    def test_bare_label_supplies_no_code(self):
        """A label word is not an identifier. Emitting it as the code would
        collide across every sibling carrying the same label."""
        sig = _heading_signal("Sub-Strand — Curiosity and Interest")
        assert sig is not None
        assert sig.code == ""
        assert sig.remainder == "Curiosity and Interest"
        assert sig.level is HierarchyLevelEnum.SUB_STRAND

    def test_identifier_after_the_separator_is_absorbed(self):
        """``<Label>: <id>`` folds to ``<Label> <id>`` — the same shape-based
        fold detector._canonicalize_code performs for the LLM's output."""
        sig = _heading_signal("Strand: 1.0 — Motivation to Learn")
        assert sig is not None
        assert sig.code == "Strand 1.0"
        assert sig.remainder == "Motivation to Learn"

    def test_whitespace_alone_closes_a_labelled_identifier(self):
        """Texas and California both print an id with no punctuation after it.
        Requiring punctuation made the pattern backtrack and split the id."""
        sig = _heading_signal("Foundation 1.1 Curiosity and Interest")
        assert sig is not None
        assert sig.code == "Foundation 1.1"
        assert sig.remainder == "Curiosity and Interest"

    def test_a_label_word_inside_a_longer_word_is_not_a_heading(self):
        assert _heading_signal("Standardized testing is not a heading") is None

    def test_numbering_depth_maps_to_level(self):
        assert _heading_signal("1. Health").level is HierarchyLevelEnum.STRAND
        assert _heading_signal("1.2 Health").level is HierarchyLevelEnum.SUB_STRAND
        assert _heading_signal("1.2.3 Health").level is HierarchyLevelEnum.INDICATOR

    def test_unterminated_single_segment_is_not_a_heading(self):
        """Without this guard every sentence opening with a capital letter and
        a space ("A blanket provides comfort") starts a heading."""
        assert _heading_signal("A blanket provides comfort") is None
        assert _heading_signal("A. Self-Concept") is not None

    def test_unterminated_multi_segment_path_is_a_heading(self):
        sig = _heading_signal("PK4.I.A.1 Child is aware of where own body is")
        assert sig is not None
        assert sig.code == "PK4.I.A.1"
        assert sig.age_band == "PK4"
        assert sig.level is HierarchyLevelEnum.INDICATOR

    def test_age_prefix_does_not_count_as_a_nesting_level(self):
        """``PK4.I.A.1`` nests three deep, not four — the age token is a
        column, not a level."""
        assert _heading_signal("PK4.I.A.1 Child").depth == 3
        assert _heading_signal("I.A.1 Child").depth == 3

    def test_lettered_item_is_a_leaf(self):
        sig = _heading_signal("a. Demonstrates self-confidence.")
        assert sig is not None
        assert sig.code == "a"
        assert sig.level is HierarchyLevelEnum.INDICATOR


# --------------------------------------------------------------------------
# Trailing structural nouns
# --------------------------------------------------------------------------

class TestTrailingLabel:
    def test_trailing_noun_is_stripped_and_read_as_a_level(self):
        title, level = _strip_trailing_label("Social and Emotional Development Domain")
        assert title == "Social and Emotional Development"
        assert level is HierarchyLevelEnum.DOMAIN

    @pytest.mark.parametrize("title", [
        "Self-Awareness and Emotional Skills",
        "Mathematics Knowledge & Skills",
        "Curiosity and Interest",
    ])
    def test_content_nouns_at_the_end_of_a_title_survive(self, title):
        """⚠️ REGRESSION GUARD. TRAILING_LABEL_WORDS must stay a strict subset
        of LABEL_LEVELS. Stripping every label word from the end of a title
        deleted "Skills" from Arizona's strand and cost it two golden matches.
        """
        assert _strip_trailing_label(title) == (title, None)

    def test_trailing_label_words_are_a_strict_subset_of_label_levels(self):
        assert set(TRAILING_LABEL_WORDS) < set(LABEL_LEVELS)


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

class TestLayout:
    def test_columns_are_read_in_order_not_interleaved(self):
        """A multi-column spread flattens into interleaved reading order in the
        extraction. Without column reconstruction every heuristic downstream
        fails for the wrong reason."""
        blocks = [
            _block("left one", top=0.20, left=0.06, width=0.2),
            _block("right one", top=0.20, left=0.60, width=0.2),
            _block("left two", top=0.25, left=0.06, width=0.2),
            _block("right two", top=0.25, left=0.60, width=0.2),
        ]
        got = [ln.text for ln in _reading_order(_to_lines(blocks))]
        assert got == ["left one", "left two", "right one", "right two"]

    def test_a_full_width_line_breaks_the_bands(self):
        blocks = [
            _block("col a", top=0.10, left=0.06, width=0.2),
            _block("col b", top=0.10, left=0.60, width=0.2),
            _block("a paragraph spanning the whole measure", top=0.30,
                   left=0.06, width=0.88),
            _block("col c", top=0.50, left=0.06, width=0.2),
        ]
        got = [ln.text for ln in _reading_order(_to_lines(blocks))]
        assert got.index("col b") < got.index("a paragraph spanning the whole measure")
        assert got.index("a paragraph spanning the whole measure") < got.index("col c")

    def test_microtype_furniture_is_dropped_wherever_it_sits(self):
        """Colorado prints per-page navigation tabs at ~55% of body size, as far
        down as 0.086 of the page. A margin-position test let 160 of them
        through as domains; the size ratio is the reliable signal."""
        body = [_block(f"1.{i} Some heading here", top=0.2 + i * 0.05, height=0.014)
                for i in range(1, 6)]
        tabs = [_block(f"NAVTAB{i}", top=0.05 + i * 0.01, height=0.007, width=0.05)
                for i in range(6)]
        result = detect_structure_baseline(tabs + body)
        titles = " ".join(e.title for e in result.elements)
        assert "NAVTAB" not in titles

    def test_a_display_heading_does_not_absorb_smaller_lines_below_it(self):
        """"Physical Development & Health" + "Examples" + "Children may." fused
        into one title until continuation required matching type size."""
        blocks = [
            _block("Physical Development & Health", top=0.18, left=0.39,
                   height=0.0177, width=0.22),
            _block("Examples", top=0.208, left=0.291, height=0.0141, width=0.06),
        ]
        result = detect_structure_baseline(blocks)
        assert any(e.title == "Physical Development & Health" for e in result.elements)


# --------------------------------------------------------------------------
# Age bands
# --------------------------------------------------------------------------

class TestAgeBands:
    @pytest.mark.parametrize("line,expected", [
        ("Early (3 to 4 ½ Years)", True),
        ("Later (4 to 5 1/2 Years)", True),
        ("Aim for 10-13 hours of sleep per day (including naps).", False),
        ("Academic Standards are noted with an asterisk (*)", False),
        ("Discovering", False),   # a proficiency band, not an age range
    ])
    def test_header_shape_is_recognized_without_a_vocabulary(self, line, expected):
        assert _is_age_band_header(line) is expected

    def test_a_heading_over_two_bands_emits_one_element_per_band(self):
        """The golden sets annotate a separate indicator per age-band column,
        so a baseline that emits one element can never match either."""
        blocks = [
            _block("Foundation 1.2 Initiative", top=0.20, left=0.089, width=0.21),
            _block("Early (3 to 4 ½ Years)", top=0.25, left=0.089, width=0.167),
            _block("Later (4 to 5 1/2 Years)", top=0.25, left=0.504, width=0.168),
        ]
        result = detect_structure_baseline(blocks)
        variants = [e for e in result.elements if e.title == "Initiative"]
        assert len(variants) == 2
        assert {e.age_band for e in variants} == {
            "Early (3 to 4 ½ Years)", "Later (4 to 5 1/2 Years)"
        }
        assert {e.code for e in variants} == {"Foundation 1.2"}


# --------------------------------------------------------------------------
# Anti-overfit guards
# --------------------------------------------------------------------------

class TestStaysDocumentAgnostic:
    def test_no_state_name_appears_in_the_source(self):
        """⚠️ THE LOAD-BEARING TEST. A baseline with a per-document branch
        measures nothing: it would report how well someone hand-tuned rules
        against six known files, not what rules achieve on a new document. The
        same prohibition CLAUDE.md places on detector.py, for the same reason.

        Prose in comments and docstrings is exempt — the module explains WHICH
        document motivated a rule, which is the record that lets a reader check
        the rule for overfitting. Only executable lines are scanned.
        """
        src = Path(rule_based.__file__).read_text().split("\n")
        code = []
        in_doc = False
        for line in src:
            stripped = line.strip()
            if stripped.count('"""') == 1:
                in_doc = not in_doc
                continue
            if in_doc or stripped.startswith("#") or stripped.startswith('"""'):
                continue
            code.append(line.split("#")[0])
        joined = "\n".join(code)
        names = ["Arizona", "California", "Colorado", "Texas", "Nevada", "Kentucky",
                 "AZ", "CA", "CO", "TX", "NV", "KY"]
        found = [n for n in names if re.search(rf"\b{n}\b", joined)]
        assert not found, f"state-specific token(s) in executable code: {found}"

    def test_it_is_deterministic(self):
        """Unlike the LLM detector, two runs must agree exactly — this is what
        licenses grading the baseline from a single run."""
        blocks = [
            _block("Strand 1: Self-Awareness", top=0.2),
            _block("a. Demonstrates self-confidence.", top=0.3),
        ]
        first = detect_structure_baseline(blocks)
        second = detect_structure_baseline(blocks)
        assert [e.model_dump() for e in first.elements] == \
               [e.model_dump() for e in second.elements]

    def test_empty_input_reports_an_error_like_the_llm_detector_does(self):
        result = detect_structure_baseline([])
        assert result.status == "error"
        assert result.elements == []


# --------------------------------------------------------------------------
# The eval_detector seam
# --------------------------------------------------------------------------

class TestGradedByTheSameSuite:
    """``evaluate_state`` grew two optional parameters so a non-LLM detector
    could be graded by the LLM's own path. Both defaults must be unchanged, and
    neither may reach Bedrock when the baseline is the detector under test."""

    def test_detect_fn_defaults_to_the_llm_runner(self):
        import inspect
        from evaluation.eval_detector import evaluate_state
        params = inspect.signature(evaluate_state).parameters
        assert params["detect_fn"].default is None
        assert params["grade_depth_map_pass"].default is True

    def test_baseline_records_the_depth_map_as_ablated_without_calling_bedrock(
        self, tmp_path, monkeypatch
    ):
        import json
        import evaluation.eval_detector as ed
        from evaluation.baselines.eval_baseline import DEPTH_MAP_DETAIL, run_baseline

        def _explode(*_a, **_k):  # pragma: no cover - must never run
            raise AssertionError("infer_depth_map must not be called for the baseline")

        monkeypatch.setattr(ed, "infer_depth_map", _explode)

        extraction = tmp_path / "ZZ-extraction.json"
        extraction.write_text(json.dumps({"blocks": [
            _block("Strand 1: Self-Awareness", top=0.2).model_dump(),
        ]}))
        golden = tmp_path / "ZZ.json"
        golden.write_text(json.dumps({
            "elements": [{"test_case_id": "ZZ-STR-01", "level": "strand",
                          "code": "Strand 1", "title": "Self-Awareness"}],
            "expected_depth_map": {"doc_depths": [{"canonical_level": "strand"}]},
            "regression_cases": [],
        }))

        rep, _ = ed.evaluate_state(
            "ZZ", extraction, golden, use_cache=False, stability_runs=1,
            detect_fn=run_baseline, grade_depth_map_pass=False,
            depth_map_skip_detail=DEPTH_MAP_DETAIL,
        )
        assert rep.depth_map_passed is None
        assert rep.depth_map_detail == DEPTH_MAP_DETAIL
        assert rep.matched == 1
        # And the report serializes through eval_detector's own function, so a
        # baseline report is shape-identical to an LLM one.
        assert set(ed.report_to_dict(rep)) >= {
            "state", "recall", "precision", "code_accuracy", "per_level", "confusion",
        }
