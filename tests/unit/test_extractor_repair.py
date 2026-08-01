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


# --- Regression: cosmetic character variants must not defeat the match ---
#
# The AZ 2018 PDF's text layer uses typographic punctuation (U+2019 curly
# apostrophe) where Textract OCRs plain ASCII ("Children's"). The original
# exact `find` therefore missed on 113 of 135 eligible AZ lines, leaving the
# fusion in place. Matching now runs over a folded view of both sides.


def test_matches_across_curly_vs_straight_apostrophe():
    page = "Children’s emotional development is built into their brains"
    block = _line("Children's emotional developmentis built into their brains")
    out = _repair_line_text(block, *_index(page))
    assert out == "Children's emotional development is built into their brains"


def test_folded_match_keeps_the_blocks_own_characters():
    # The page says "don’t"; the block says "don't". The repair fixes the
    # spacing but must NOT swap in the text layer's apostrophe.
    page = "the children don’t always share their toys willingly"
    block = _line("the children don't alwaysshare their toys willingly")
    out = _repair_line_text(block, *_index(page))
    assert out == "the children don't always share their toys willingly"
    assert "’" not in out


def test_matches_across_en_dash_vs_hyphen():
    page = "social – emotional growth for ages three to five years"
    block = _line("social - emotionalgrowth for ages three to five years")
    out = _repair_line_text(block, *_index(page))
    assert out == "social - emotional growth for ages three to five years"


# --- Regression: fusion sitting exactly on the text layer's line wrap ---


def test_repairs_fusion_at_text_layer_line_wrap_boundary():
    # This is the AZ "andphysical" case: the missing space is precisely where
    # the PDF wraps the line, so the boundary evidence is a newline, not a
    # space. It must still yield exactly one space.
    page = "Relationships that provide social, emotional, and\nphysical security promote learning"
    block = _line(
        "Relationships that provide social, emotional, andphysical security promote learning"
    )
    out = _repair_line_text(block, *_index(page))
    assert out == (
        "Relationships that provide social, emotional, and physical security promote learning"
    )
    assert "\n" not in out


def test_multi_character_whitespace_run_collapses_to_one_space():
    page = "early learning\n\n   standards guide  \t classroom practice daily"
    block = _line("early learningstandards guide classroom practice daily")
    out = _repair_line_text(block, *_index(page))
    assert out == "early learning standards guide classroom practice daily"


# --- Regression: invisible characters are not word boundaries ---


def test_soft_hyphen_line_wrap_does_not_introduce_a_space():
    # A soft hyphen at a wrap point marks display hyphenation of a single
    # word. Dropping it (rather than treating it as whitespace) keeps the word
    # joined, matching what Textract read.
    page = "developmen­tally appropriate practice for young children"
    block = _line("developmentally appropriate practice for young children")
    out = _repair_line_text(block, *_index(page))
    assert out == "developmentally appropriate practice for young children"


def test_zero_width_space_is_not_a_word_boundary():
    page = "phonological​awareness skills develop over the preschool years"
    block = _line("phonologicalawareness skills develop over the preschool years")
    out = _repair_line_text(block, *_index(page))
    assert out == "phonologicalawareness skills develop over the preschool years"


# --- Safety properties that must survive the relaxed matching ---


def test_folding_does_not_relax_the_uniqueness_guard():
    # Two occurrences that differ only by apostrophe style now fold to the same
    # key. That makes the match ambiguous, and ambiguous means hands off.
    page = "the child’s early growth matters and the child's early growth matters"
    block = _line("the child's earlygrowth matters")
    assert _repair_line_text(block, *_index(page)) is None


def test_never_changes_a_non_whitespace_character():
    page = "a child’s curiosity — sustained — drives “deep” learning"
    block = _line("a child's curiosity - sustained - drives \"deep\"learning")
    out = _repair_line_text(block, *_index(page))
    assert "".join(out.split()) == "".join(block.text.split())
    assert out == 'a child\'s curiosity - sustained - drives "deep" learning'


def test_folding_does_not_match_genuinely_different_text():
    page = "vocabulary development supports later reading comprehension skills"
    block = _line("mathematics reasoning supports later problem solving skills")
    assert _repair_line_text(block, *_index(page)) is None
