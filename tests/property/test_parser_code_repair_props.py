"""Safety properties for the parser's deterministic code repairs.

The three repairs in `parser.py` rewrite the code that becomes an Aurora
primary key, and they run on every row of every document — including documents
nobody has annotated. Their unit tests pin the shapes we have SEEN; these
properties pin what must hold for shapes we have not.

The governing invariant is that a repair may only ever move a row toward a
well-formed code. It must never manufacture a new kind of malformation, and it
must never break a row that was already correct — a repair that can damage a
good row is worse than no repair, because the defect it targets is intermittent
while the damage would be unconditional.
"""

from hypothesis import given, strategies as st

from els_pipeline.parser import (
    _collapse_duplicated_indicator_segment,
    _collapse_duplicated_parent_segment,
    _delabel_parent_code,
    _qualify_bare_indicator_code,
)

# Code-shaped tokens: the alphabet real codes are drawn from, plus a space so
# the malformed `<Label> <id>` shape is reachable.
_SEGMENT = st.text(alphabet="ABCD0123 ", min_size=1, max_size=4).filter(lambda t: t.strip())
_CODE = st.lists(_SEGMENT, min_size=1, max_size=4).map(".".join)
_OPTIONAL_CODE = st.one_of(st.none(), _CODE)


def _repair(domain, strand, sub_strand, indicator):
    strand = _delabel_parent_code(strand, domain)
    sub_strand = _delabel_parent_code(sub_strand, domain)
    sub, ind = _collapse_duplicated_parent_segment(strand, sub_strand, indicator)
    ind = _collapse_duplicated_indicator_segment(strand, sub, ind)
    ind = _qualify_bare_indicator_code(domain, strand, sub, ind)
    return sub, ind


def _extends_nearest_ancestor(domain, strand, sub, ind):
    ancestor = sub or strand or domain
    return not ancestor or ind.startswith(ancestor + ".")


class TestRepairsNeverMakeARowWorse:
    @given(_CODE, _OPTIONAL_CODE, _OPTIONAL_CODE, _CODE)
    def test_whitespace_is_never_introduced(self, domain, strand, sub_strand, indicator):
        """A repair must not inject whitespace into a code that lacked it —
        that would trade a `not nested` rejection for a `whitespace` one and
        hide the real cause."""
        sub, ind = _repair(domain, strand, sub_strand, indicator)
        if not any(c.isspace() for c in indicator):
            assert not any(c.isspace() for c in ind)
        if sub_strand is not None and not any(c.isspace() for c in sub_strand):
            assert not any(c.isspace() for c in sub)

    @given(_CODE, _OPTIONAL_CODE, _OPTIONAL_CODE, _CODE)
    def test_an_already_valid_chain_is_left_alone(self, domain, strand, sub_strand, indicator):
        """If the row already satisfies the validator's nesting condition, no
        repair may touch it."""
        if not _extends_nearest_ancestor(domain, strand, sub_strand, indicator):
            return
        assert _repair(domain, strand, sub_strand, indicator) == (sub_strand, indicator)

    @given(_CODE, _OPTIONAL_CODE, _OPTIONAL_CODE, _CODE)
    def test_repairs_are_idempotent(self, domain, strand, sub_strand, indicator):
        """Re-running the chain over its own output must be a no-op, so a
        retried or re-merged row cannot drift."""
        sub, ind = _repair(domain, strand, sub_strand, indicator)
        assert _repair(domain, strand, sub, ind) == (sub, ind)

    @given(_CODE, _OPTIONAL_CODE, _OPTIONAL_CODE, _CODE)
    def test_nesting_is_never_broken(self, domain, strand, sub_strand, indicator):
        """The indicator's relationship to its ancestor may only improve."""
        before = _extends_nearest_ancestor(domain, strand, sub_strand, indicator)
        sub, ind = _repair(domain, strand, sub_strand, indicator)
        after = _extends_nearest_ancestor(domain, strand, sub, ind)
        assert after or not before

    @given(_CODE, _OPTIONAL_CODE, _OPTIONAL_CODE, _CODE)
    def test_a_code_is_never_emptied_or_nulled(self, domain, strand, sub_strand, indicator):
        sub, ind = _repair(domain, strand, sub_strand, indicator)
        assert ind
        assert (sub is None) == (sub_strand is None)
