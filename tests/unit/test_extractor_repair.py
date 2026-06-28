"""Unit tests for text-layer spacing repair in the extractor.

These cover the pure matching/repair logic (`_build_despaced_index`,
`_repair_line_text`) with synthetic page text — no PDF or S3 needed.
"""

from els_pipeline.extractor import _build_despaced_index, _repair_line_text
from els_pipeline.models import TextBlock


def _line(text: str, page: int = 1) -> TextBlock:
    return TextBlock(
        text=text, page_number=page, block_type="LINE", confidence=0.99, geometry={}
    )


def _index(page_text: str):
    despaced, idx_map = _build_despaced_index(page_text)
    return page_text, despaced, idx_map


def test_repairs_fused_words_from_text_layer():
    page = "It sets a firm foundation on which all other learning takes place."
    block = _line("sets a firmfoundation on which all other learning takes place.")
    out = _repair_line_text(block, *_index(page))
    assert out == "sets a firm foundation on which all other learning takes place."


def test_only_whitespace_ever_changes():
    page = "the quick brown fox jumps over the lazy dog every morning"
    block = _line("quick brownfox jumps over thelazy dog every morning")
    out = _repair_line_text(block, *_index(page))
    # De-spaced characters must be identical — only spacing differs.
    assert "".join(out.split()) == "".join(block.text.split())
    assert out == "quick brown fox jumps over the lazy dog every morning"


def test_collapses_text_layer_newlines_to_single_line():
    page = "children develop an increasing\ncapacity to experience emotions"
    block = _line("children develop an increasingcapacity to experience emotions")
    out = _repair_line_text(block, *_index(page))
    assert "\n" not in out
    assert out == "children develop an increasing capacity to experience emotions"


def test_returns_none_when_not_found():
    page = "completely unrelated sentence in the text layer here"
    block = _line("this line does not appear on the page at all")
    assert _repair_line_text(block, *_index(page)) is None


def test_returns_none_for_short_lines():
    # Below _MIN_REPAIR_KEY_LEN — too ambiguous to match safely.
    page = "a cat sat on the mat in the warm afternoon sun today"
    block = _line("a cat sat")
    assert _repair_line_text(block, *_index(page)) is None


def test_returns_none_on_ambiguous_duplicate_match():
    # The line's de-spaced form occurs twice on the page → skip to avoid
    # adopting the wrong occurrence's spacing.
    page = "phonological awareness matters phonological awareness matters"
    block = _line("phonologicalawareness matters")
    assert _repair_line_text(block, *_index(page)) is None


def test_ignores_non_line_blocks():
    page = "the alphabet system supports early literacy development greatly"
    cell = TextBlock(
        text="alphabet system supports early literacy",
        page_number=1,
        block_type="TABLE_CELL",
        confidence=0.99,
        geometry={},
    )
    assert _repair_line_text(cell, *_index(page)) is None


def test_leaves_already_correct_lines_unchanged():
    page = "children learn to discriminate between sounds in spoken language"
    block = _line("children learn to discriminate between sounds in spoken language")
    out = _repair_line_text(block, *_index(page))
    # Match is exact; re-spacing yields identical text (caller treats == as no-op).
    assert out == block.text
