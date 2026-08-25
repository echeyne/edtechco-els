"""Pass-1's sample must not lose a nesting DEPTH.

`infer_depth_map` reads a sample of the document and reports how many depths it
uses; every element's level is then assigned from that map, so a depth missing
from the sample is a depth missing from the whole run.

The old sampler took every Nth block, which keeps a line with probability
1/stride no matter how load-bearing it is. The rarest lines in a document are
the headings that open a section — exactly the evidence for the TOP of the
hierarchy — while body prose survives on volume alone.

Measured on the 52-page Kentucky document (1741 blocks, stride 4): 7 of the 9
bare content-area headings were dropped, Pass-1 never saw a bare heading beside
its own "<Area> Standard N" line, and reported a 3-level hierarchy for a
4-level document. Every level shifted up one, the domain level was never
emitted, and `validator._validate_code_shape` rejected 102 of 202 standards.
The 15-page subset of the same document stayed under the token budget, was
never sampled, and reported the correct 4 levels.

`test_a_rare_layout_bucket_survives` is the canary: if it fails, the sampler
has gone back to letting volume decide what Pass-1 sees.
"""

from els_pipeline.detector import (
    DEPTH_MAP_SAMPLE_TOKENS,
    _layout_bucket_key,
    _sample_blocks_for_depth_map,
    estimate_tokens,
)
from els_pipeline.models import TextBlock


def _block(text, left=0.21, page=1):
    geometry = (
        {"BoundingBox": {"Left": left, "Top": 0.1, "Width": 0.5, "Height": 0.02}}
        if left is not None
        else {}
    )
    return TextBlock(
        text=text, page_number=page, block_type="LINE", confidence=0.99, geometry=geometry
    )


def _kentucky_shaped_document():
    """A document shaped like KY: a handful of centered section headings buried
    under a great deal of body prose at one indent."""
    blocks = []
    for section in range(9):
        page = section * 6 + 1
        blocks.append(_block(f"Content Area {section}", left=0.39, page=page))
        blocks.append(_block(f"Content Area {section} Standard 1: Does a thing.", left=0.12, page=page))
        for i in range(180):
            blocks.append(
                _block(
                    f"Body prose line {i} for section {section} with enough words to weigh something.",
                    left=0.21,
                    page=page + i // 40,
                )
            )
    return blocks


class TestRareDepthsSurvive:
    def test_a_rare_layout_bucket_survives(self):
        """THE CANARY. A depth that occurs once per section must reach Pass-1."""
        blocks = _kentucky_shaped_document()
        assert sum(estimate_tokens(b.text) for b in blocks) > DEPTH_MAP_SAMPLE_TOKENS

        sample = _sample_blocks_for_depth_map(blocks)
        headings = [b for b in sample if b.text.startswith("Content Area") and "Standard" not in b.text]
        assert len(headings) == 9, f"lost section headings: only {len(headings)}/9 sampled"

    def test_the_pairing_that_distinguishes_two_depths_is_visible(self):
        """A bare heading and its own numbered child must both be sampled, or
        Pass-1 cannot tell they are two depths rather than one."""
        sample = _sample_blocks_for_depth_map(_kentucky_shaped_document())
        pages = {b.page_number for b in sample if b.text.startswith("Content Area") and "Standard" not in b.text}
        paired = {b.page_number for b in sample if "Standard 1:" in b.text} & pages
        assert paired, "no page shows a bare heading beside its numbered child"

    def test_bulk_prose_is_still_sampled(self):
        """Rare buckets get a floor, not the whole budget — the body must also
        be represented or Pass-1 cannot see the deepest depth."""
        sample = _sample_blocks_for_depth_map(_kentucky_shaped_document())
        assert sum(1 for b in sample if b.text.startswith("Body prose")) > 50


class TestSamplingInvariants:
    def test_a_document_under_budget_is_returned_whole(self):
        """The KY subset run passed 26/26 precisely because it was never
        sampled. Small documents must keep that exact behaviour."""
        blocks = [_block(f"line {i}") for i in range(5)]
        assert _sample_blocks_for_depth_map(blocks) == blocks

    def test_budget_is_respected(self):
        sample = _sample_blocks_for_depth_map(_kentucky_shaped_document())
        assert sum(estimate_tokens(b.text) for b in sample) <= DEPTH_MAP_SAMPLE_TOKENS

    def test_document_order_is_preserved_without_duplicates(self):
        blocks = _kentucky_shaped_document()
        sample = _sample_blocks_for_depth_map(blocks)
        positions = [blocks.index(b) for b in sample]
        assert positions == sorted(positions)
        assert len(set(id(b) for b in sample)) == len(sample)

    def test_the_sample_spans_the_whole_document(self):
        """The old sampler stopped once the budget filled, silently dropping the
        tail (pages 1-46 of KY's 52). A depth introduced late must still land."""
        blocks = _kentucky_shaped_document()
        sample = _sample_blocks_for_depth_map(blocks)
        assert max(b.page_number for b in sample) == max(b.page_number for b in blocks)

    def test_empty_input(self):
        assert _sample_blocks_for_depth_map([]) == []


class TestLayoutBucketKey:
    def test_left_edge_is_rounded_to_what_the_prompt_prints(self):
        """`_serialize_blocks_for_prompt` renders x to 2dp, so a bucket must be
        one of the values the model actually reads, not a private notion."""
        assert _layout_bucket_key(_block("x", left=0.1234)) == 0.12
        assert _layout_bucket_key(_block("x", left=0.1249)) == _layout_bucket_key(_block("y", left=0.1201))

    def test_geometry_free_blocks_split_by_line_shape(self):
        """A scanned page has no left edge to group on. Shape alone — word count
        and final character — separates a heading from prose."""
        heading = _layout_bucket_key(_block("Approaches to Learning", left=None))
        prose = _layout_bucket_key(
            _block("This is a full sentence of body prose that runs on.", left=None)
        )
        assert heading != prose
        assert heading == ("no-geometry", True)
        assert prose == ("no-geometry", False)

    def test_shape_fallback_reads_no_vocabulary(self):
        """Two unrelated short headings must bucket together — the rule keys on
        shape, never on any document's words."""
        assert _layout_bucket_key(_block("Creative Arts", left=None)) == _layout_bucket_key(
            _block("Zzz Qqq", left=None)
        )
