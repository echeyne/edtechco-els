"""The collision fallback must produce the same primary keys on every run.

`disambiguate_colliding_standards` resolves duplicate indicator codes by
ancestor first, and falls back to a numeric suffix for rows no parent
separates. That fallback hands one row the bare code and the next a `.2`, and
both become Aurora primary keys via `standard_id`.

It used to enumerate the colliding group in ARRIVAL order, so which row got the
suffix depended on chunk and batch scheduling — the same document could write
different keys on different runs. That is precisely the order-dependence the
resolver was introduced to remove, reintroduced inside its own last resort.

Live case: `pipeline-US-KY-2021-full08252026-04` page 30, where "Labels
pictures or produces simple texts using scribble writing" and "…using
letter-like forms" both abbreviate to `LPPST` under rule 4's 5-char cap,
because everything distinguishing the two titles falls past the cap.
"""

import random

from els_pipeline.models import HierarchyLevel, NormalizedStandard
from els_pipeline.parser import disambiguate_colliding_standards


def _standard(name, page, source_text, code="LEL.4.2.LPPST"):
    return NormalizedStandard(
        standard_id=f"US-KY-2021-{code}",
        country="US",
        state="KY",
        version_year=2021,
        domain=HierarchyLevel(code="LEL", name="Language and Early Literacy"),
        strand=HierarchyLevel(code="LEL.4", name="Writing"),
        sub_strand=HierarchyLevel(code="LEL.4.2", name="Produces marks"),
        indicator=HierarchyLevel(code=code, name=name),
        age_band="36-60",
        source_page=page,
        source_text=source_text,
    )


def _assignment(specs):
    """Resolve a FRESH set of standards built from `specs` and map name -> id.

    Rebuilt every call on purpose: `disambiguate_colliding_standards` mutates
    the objects it is given, so reusing them across calls would leave the second
    call with no collision left to resolve — and the comparison would pass
    against any implementation.
    """
    out = disambiguate_colliding_standards(
        [_standard(*spec) for spec in specs], "US", "KY", 2021
    )
    return {s.indicator.name: s.standard_id for s in out}


class TestCollisionFallbackIsDeterministic:
    def _colliding_pair(self):
        return [
            ("Labels pictures using scribble writing.", 30, "a. scribble writing"),
            ("Labels pictures using letter-like forms.", 30, "b. letter-like forms"),
        ]

    def test_the_same_rows_get_the_same_ids_regardless_of_input_order(self):
        """THE CANARY. Reversing the input must not move the suffix."""
        specs = self._colliding_pair()
        assert _assignment(specs) == _assignment(list(reversed(specs)))

    def test_stable_across_many_shuffles(self):
        specs = [(f"Indicator variant {i}.", 30, f"{i}. variant") for i in range(5)]
        baseline = _assignment(specs)
        rng = random.Random(0)
        for _ in range(10):
            shuffled = specs[:]
            rng.shuffle(shuffled)
            assert _assignment(shuffled) == baseline

    def test_the_collision_is_actually_resolved(self):
        assigned = _assignment(self._colliding_pair())
        assert len(set(assigned.values())) == 2

    def test_document_order_decides_which_row_keeps_the_bare_code(self):
        """The row printed EARLIER in the document keeps the unsuffixed code."""
        assigned = _assignment(
            [("Later one.", 30, "b. later"), ("Earlier one.", 12, "a. earlier")]
        )
        assert assigned["Earlier one."] == "US-KY-2021-LEL.4.2.LPPST"
        assert assigned["Later one."] == "US-KY-2021-LEL.4.2.LPPST.2"

    def test_rows_a_parent_separates_do_not_reach_the_fallback(self):
        """The ancestor pass still wins where it applies — the numeric suffix is
        a last resort, not the primary mechanism."""
        a = _standard("One.", 10, "a.")
        b = _standard("Two.", 11, "b.")
        b.strand = HierarchyLevel(code="LEL.5", name="Other strand")
        out = disambiguate_colliding_standards([a, b], "US", "KY", 2021)
        assigned = {s.indicator.name: s.standard_id for s in out}
        assert not any(v.endswith(".2") for v in assigned.values()), assigned
