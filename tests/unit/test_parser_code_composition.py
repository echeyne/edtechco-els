"""Deterministic repair of the code the parser LLM composes.

`standard_id` is `{country}-{state}-{year}-{indicator_code}`, so a malformed
indicator code is a malformed Aurora primary key. The parser composes that code
from a chain of headings and gets it right only most of the time, which is the
same argument that put `derive_code_from_title` in Python: a prompt rule lowers
the rate, but a primary key needs zero.

Three defects, all measured on the KY full-document run of 2026-08-25
(`pipeline-US-KY-2021-full08252026`, 202 standards):

  1. A DUPLICATED parent position. "Benchmark 1.1" under "…Standard 1" carries
     the standard inside its own id, so composing it onto the whole strand code
     counts the standard twice — `AL.1.1.1` where the document means `AL.1.1`.
     78 of 202 rows. The detector input was uniform (all 51 sub_strands arrived
     as `Benchmark N.N`) and the parser still emitted both shapes inside one
     domain, so this is sampling, not a rule difference.
  2. The same duplication in the INDICATOR only, where the sub_strand came out
     right (`SCIE.1.3` with `SCIE.1.1.3.DCBO`). 1 row.
  3. A BARE indicator code with the chain dropped entirely — `UMNDW` where the
     row's own ancestors say `AL.2.2.UMNDW`. 45 of the 49 rows the validator
     rejected.

Together these took the run from 153/202 passing `_validate_code_shape` to
202/202, and from 13/26 to 26/26 against the KY parser golden — while changing
ZERO rows in two full six-state production runs (524 rows) and zero of the 106
annotated standards in the six goldens. `TestGoldenShapesAreUntouched` and
`test_nevada_sub_strand_may_still_break_the_chain` are the canaries.
"""

import glob
import json

import pytest

from els_pipeline.parser import (
    _collapse_duplicated_indicator_segment,
    _collapse_duplicated_parent_segment,
    _qualify_bare_indicator_code,
)


def _repair(domain, strand, sub_strand, indicator):
    """The three repairs in the order `parse_llm_response` applies them."""
    sub, ind = _collapse_duplicated_parent_segment(strand, sub_strand, indicator)
    ind = _collapse_duplicated_indicator_segment(strand, sub, ind)
    ind = _qualify_bare_indicator_code(domain, strand, sub, ind)
    return sub, ind


class TestDuplicatedParentSegment:
    def test_kentucky_benchmark_carries_its_standard(self):
        """`Benchmark 1.1` under `Standard 1` is AL.1.1, not AL.1.1.1."""
        assert _repair("AL", "AL.1", "AL.1.1.1", "AL.1.1.1.EASPT") == ("AL.1.1", "AL.1.1.EASPT")

    def test_a_later_benchmark_in_the_same_standard(self):
        assert _repair("CA", "CA.1", "CA.1.1.4", "CA.1.1.4.UVASE") == ("CA.1.4", "CA.1.4.UVASE")

    def test_an_ordinary_child_position_is_left_alone(self):
        """THE GUARD. A single added segment is a normal child index — only a
        DOTTED tail whose head repeats the strand can be a duplicated position.
        Without this, every correctly-composed code would be mangled."""
        assert _repair("AL", "AL.2", "AL.2.2", "AL.2.2.ESSDP") == ("AL.2.2", "AL.2.2.ESSDP")

    def test_a_sub_strand_that_does_not_extend_its_strand_is_left_alone(self):
        """NV CANARY. Nevada's `SS.ID` deliberately does not extend `SS.1`."""
        assert _repair("SS", "SS.1", "SS.ID", "SS.ID.PK1") == ("SS.ID", "SS.ID.PK1")

    def test_repair_is_idempotent(self):
        once = _repair("AL", "AL.1", "AL.1.1.1", "AL.1.1.1.EASPT")
        assert _repair("AL", "AL.1", *once) == once


class TestIndicatorOnlyDuplication:
    def test_it_fires_when_the_sub_strand_was_composed_correctly(self):
        assert _repair("SCIE", "SCIE.1", "SCIE.1.3", "SCIE.1.1.3.DCBO") == (
            "SCIE.1.3",
            "SCIE.1.3.DCBO",
        )

    def test_it_does_not_fire_when_collapsing_would_not_repair_the_ancestry(self):
        """SELF-VERIFYING. The repair is only applied when it demonstrably makes
        the indicator extend its own sub_strand; otherwise the code is left as
        the model emitted it rather than guessed at."""
        _, ind = _repair("X", "X.1", "X.9", "X.1.1.5.ABC")
        assert ind == "X.1.1.5.ABC"

    def test_an_indicator_that_already_extends_is_untouched(self):
        assert _repair("SCIE", "SCIE.1", "SCIE.1.3", "SCIE.1.3.DCBO")[1] == "SCIE.1.3.DCBO"


class TestBareIndicatorCode:
    def test_the_chain_is_restored_from_the_nearest_ancestor(self):
        assert _qualify_bare_indicator_code("AL", "AL.2", "AL.2.2", "UMNDW") == "AL.2.2.UMNDW"

    def test_it_falls_back_through_the_chain(self):
        assert _qualify_bare_indicator_code("AL", "AL.2", None, "UMNDW") == "AL.2.UMNDW"
        assert _qualify_bare_indicator_code("AL", None, None, "UMNDW") == "AL.UMNDW"

    def test_a_dotted_indicator_is_never_prefixed(self):
        """Only a code with no separator at all is treated as bare."""
        assert _qualify_bare_indicator_code("AL", "AL.2", "AL.2.2", "AL.2.2.X") == "AL.2.2.X"

    def test_no_ancestor_means_no_repair(self):
        assert _qualify_bare_indicator_code(None, None, None, "UMNDW") == "UMNDW"

    def test_a_malformed_ancestor_is_refused(self):
        """A repair must not swap one defect for another. Prefixing a
        `<Label> <id>` code the parser failed to convert would inject
        whitespace into the primary key, and the record would then be rejected
        on the injected whitespace instead of the real cause. Observed live on
        `pipeline-US-KY-2021-full08252026-02` (3 rows)."""
        assert _qualify_bare_indicator_code("CA", "CA.1", "Benchmark 1.4", "UVASE") == "UVASE"

    def test_a_clean_ancestor_at_the_same_position_still_repairs(self):
        assert (
            _qualify_bare_indicator_code("CA", "CA.1", "CA.1.4", "UVASE") == "CA.1.4.UVASE"
        )


class TestGoldenShapesAreUntouched:
    """THE CANARY. Every annotated standard in every parser golden must survive
    all three repairs byte-identically — they exist to move malformed output
    toward the goldens, never to rewrite a hand-annotated code."""

    @pytest.mark.parametrize("path", sorted(glob.glob("evaluation/ground_truth_parser/*.json")))
    def test_no_golden_row_changes(self, path):
        changed = []
        for case in json.load(open(path))["standards"]:
            e = case["expected"]
            sub = (e.get("sub_strand") or {}).get("code")
            ind = e["indicator"]["code"]
            got = _repair(
                e["domain"]["code"], (e.get("strand") or {}).get("code"), sub, ind
            )
            if got != (sub, ind):
                changed.append((sub, ind, got))
        assert not changed, f"{path} rewrote annotated codes: {changed}"
