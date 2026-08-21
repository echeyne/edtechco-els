"""Unit tests for the validator's code-shape guard.

``standard_id`` is ``{country}-{state}-{year}-{indicator_code}``, so a
malformed indicator code is a malformed Aurora primary key. The parser emits
one intermittently, in two observed surface forms — a structural label left in
the code (CA, ``…PA.Foundation 2.3.DISC``) and the parent chain dropped
entirely (KY, a bare ``TCPHS``) — and the defect is sampling variance rather
than a code regression, so it cannot be fixed upstream by a prompt rule alone.
``_validate_code_shape`` refuses such a record at the validation boundary,
which is the chokepoint before persistence.

The regression risk these tests exist to pin down is the SECOND condition's
scoping. The nesting rule applies at the INDICATOR level only, because a
document's printed namespace may legitimately skip an intermediate level:
Nevada's sub_strand ``SS.ID`` does not extend its strand ``SS.1``. Widening the
rule to every level would reject all of Nevada, so ``test_nevada_*`` is the
canary — if it fails, the guard has stopped being document-agnostic.
"""

import pytest

from els_pipeline.validator import _validate_code_shape, validate_record


def _record(domain=None, strand=None, sub_strand=None, indicator=None, standard_id=None):
    """Minimal canonical record carrying only what the guard reads."""
    def lvl(code):
        return None if code is None else {"code": code, "name": "x"}

    return {
        "standard": {
            "standard_id": standard_id,
            "domain": lvl(domain),
            "strand": lvl(strand),
            "sub_strand": lvl(sub_strand),
            "indicator": lvl(indicator),
        },
        "metadata": {"page_number": 1},
    }


class TestAcceptsRealDocumentShapes:
    """Every shape here is taken from a hand-annotated golden and must pass."""

    @pytest.mark.parametrize(
        "state,domain,strand,sub_strand,indicator",
        [
            # KY — full 4-level, derived-abbreviation leaf.
            ("KY", "HMW", "HMW.1", "HMW.1.1", "HMW.1.1.TCPHS"),
            # CO — 3-level, no sub_strand: the indicator nests under the strand.
            ("CO", "PDH", "PDH.1", None, "PDH.1.1"),
            # CA — proficiency-column suffix on the leaf.
            ("CA", "ELD", "ELD.1.0", "ELD.1.0.VOCA", "ELD.1.0.VOCA.1.1.DISC"),
            # TX — age-range suffix on the leaf, and a lettered segment.
            ("TX", "I", "I.A", None, "I.A.2.36-48"),
            ("TX", "I", "I.B", "I.B.1", "I.B.1.a.36-48"),
        ],
    )
    def test_accepts(self, state, domain, strand, sub_strand, indicator):
        rec = _record(domain, strand, sub_strand, indicator,
                      standard_id=f"US-{state}-2021-{indicator}")
        assert _validate_code_shape(rec) == []

    def test_nevada_sub_strand_may_break_the_chain(self):
        """THE CANARY. NV codes indicators ``<domain>.<sub_strand>.PKn`` and
        gives the strand its own heading identifier, so the sub_strand ``SS.ID``
        deliberately does NOT extend the strand ``SS.1``. All 15 NV golden
        standards have this shape. The guard must accept it."""
        rec = _record("SS", "SS.1", "SS.ID", "SS.ID.PK1",
                      standard_id="US-NV-2023-SS.ID.PK1")
        assert _validate_code_shape(rec) == []

    def test_nevada_shape_survives_full_validate_record(self):
        rec = _record("SS", "SS.2", "SS.CI", "SS.CI.PK3",
                      standard_id="US-NV-2023-SS.CI.PK3")
        assert [e for e in _validate_code_shape(rec)] == []


class TestBlocksWhitespaceInCode:
    """CA, 2026-08-13: the structural label survived into the indicator code.

    Note the guard needs no list of label words — whitespace alone is the tell,
    which is why it catches 'Foundation' without knowing the word.
    """

    def test_blocks_label_left_in_indicator_code(self):
        rec = _record("ELD", "ELD.2.0", "ELD.2.0.PA",
                      "ELD.2.0.PA.Foundation 2.3.DISC",
                      standard_id="US-CA-2021-ELD.2.0.PA.Foundation 2.3.DISC")
        errors = _validate_code_shape(rec)
        assert any(e.field_path == "standard.indicator.code" for e in errors)
        assert all(e.error_type == "code_shape" for e in errors)

    def test_blocks_label_left_in_a_parent_code(self):
        rec = _record("SCI", "SCI.Strand 1", None, "SCI.Strand 1.a",
                      standard_id="US-AZ-2018-SCI.Strand 1.a")
        assert any(e.field_path == "standard.strand.code"
                   for e in _validate_code_shape(rec))

    def test_message_carries_the_chain_for_localization(self):
        rec = _record("ELD", "ELD.2.0", "ELD.2.0.PA",
                      "ELD.2.0.PA.Foundation 2.3.DISC",
                      standard_id="US-CA-2021-ELD.2.0.PA.Foundation 2.3.DISC")
        msg = _validate_code_shape(rec)[0].message
        assert "chain:" in msg and "ELD.2.0.PA" in msg


class TestBlocksUnqualifiedIndicatorCode:
    """KY, 2026-08-01 and 2026-08-16: the parent chain was dropped entirely."""

    @pytest.mark.parametrize("bare", ["TCPHS", "IHFC", "PARTO", "PSGPB"])
    def test_blocks_bare_leaf_abbreviation(self, bare):
        rec = _record("HMW", "HMW.1", "HMW.1.1", bare,
                      standard_id=f"US-KY-2021-{bare}")
        errors = _validate_code_shape(rec)
        assert any(e.field_path == "standard.indicator.code" for e in errors)

    def test_blocks_when_nearest_ancestor_is_the_strand(self):
        """A 3-level document still gets the check, against the strand."""
        rec = _record("SED", "SED.4", None, "XYZ", standard_id="US-CO-2020-XYZ")
        assert any(e.field_path == "standard.indicator.code"
                   for e in _validate_code_shape(rec))

    def test_blocks_indicator_equal_to_its_parent(self):
        """A leaf that merely repeats its parent extends nothing."""
        rec = _record("HMW", "HMW.1", "HMW.1.1", "HMW.1.1",
                      standard_id="US-KY-2021-HMW.1.1")
        assert any(e.field_path == "standard.indicator.code"
                   for e in _validate_code_shape(rec))


class TestBlocksIdCodeDesync:
    def test_blocks_standard_id_not_ending_in_indicator_code(self):
        rec = _record("HMW", "HMW.1", "HMW.1.1", "HMW.1.1.TCPHS",
                      standard_id="US-KY-2021-HMW.1.1.SOMETHINGELSE")
        assert any(e.field_path == "standard.standard_id"
                   for e in _validate_code_shape(rec))


class TestIntegrationWithValidateRecord:
    """The guard must actually make the record invalid, because that is what
    stops it reaching Aurora: `validation_handler` writes an S3 record only for
    a valid result, and `persister.persist_records` reads only those keys."""

    def _full(self, indicator_code, standard_id):
        return {
            "country": "US",
            "state": "KY",
            "document": {
                "title": "t", "version_year": 2021, "source_url": "u",
                "age_band": "36-60", "publishing_agency": "a",
            },
            "standard": {
                "standard_id": standard_id,
                "domain": {"code": "HMW", "name": "Health/Mental Wellness"},
                "strand": {"code": "HMW.1", "name": "s"},
                "sub_strand": {"code": "HMW.1.1", "name": "ss"},
                "indicator": {"code": indicator_code, "name": "i"},
            },
            "metadata": {"page_number": 6},
        }

    def test_malformed_record_is_invalid(self):
        result = validate_record(self._full("TCPHS", "US-KY-2021-TCPHS"))
        assert result.is_valid is False
        assert result.record is None
        assert any(e.error_type == "code_shape" for e in result.errors)

    def test_well_formed_record_is_valid(self):
        result = validate_record(
            self._full("HMW.1.1.TCPHS", "US-KY-2021-HMW.1.1.TCPHS")
        )
        assert result.is_valid is True


class TestDoesNotDoubleReportSchemaProblems:
    """A missing or blank code is `_validate_schema`'s finding; the shape guard
    stays quiet so one defect does not become two errors."""

    def test_blank_indicator_code_is_not_reported_by_the_shape_guard(self):
        rec = _record("HMW", "HMW.1", "HMW.1.1", "", standard_id="US-KY-2021-")
        assert _validate_code_shape(rec) == []

    def test_missing_levels_are_tolerated(self):
        assert _validate_code_shape({"standard": {}}) == []
        assert _validate_code_shape({}) == []
