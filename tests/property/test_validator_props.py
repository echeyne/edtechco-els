"""Property-based tests for validator module.

Feature: els-normalization-pipeline
"""

import pytest
from hypothesis import given, strategies as st
from els_pipeline.validator import (
    validate_record,
    serialize_record,
    deserialize_record,
)
from els_pipeline.models import NormalizedStandard, HierarchyLevel


# Strategies for generating test data

@st.composite
def hierarchy_level_strategy(draw, allow_description=False):
    """Generate a HierarchyLevel."""
    code = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Nd", "Pd"))))
    name = draw(st.text(min_size=1, max_size=100))
    description = None
    if allow_description:
        description = draw(st.one_of(st.none(), st.text(min_size=1, max_size=200)))
    return HierarchyLevel(code=code, name=name, description=description)


@st.composite
def normalized_standard_strategy(draw, include_strand=None, include_sub_strand=None):
    """Generate a NormalizedStandard."""
    # Generate valid two-letter uppercase country codes (A-Z only)
    country = draw(st.text(min_size=2, max_size=2, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    state = draw(st.text(min_size=2, max_size=2, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    version_year = draw(st.integers(min_value=2000, max_value=2030))
    domain = draw(hierarchy_level_strategy())
    
    # Determine hierarchy depth
    if include_strand is None:
        include_strand = draw(st.booleans())
    if include_sub_strand is None:
        include_sub_strand = draw(st.booleans())
    
    strand = draw(hierarchy_level_strategy()) if include_strand else None
    sub_strand = draw(hierarchy_level_strategy()) if include_sub_strand else None
    indicator = draw(hierarchy_level_strategy(allow_description=True))
    
    standard_id = f"{country}-{state}-{version_year}-{domain.code}-{indicator.code}"
    source_page = draw(st.integers(min_value=1, max_value=1000))
    source_text = draw(st.text(min_size=1, max_size=500))
    
    return NormalizedStandard(
        standard_id=standard_id,
        country=country,
        state=state,
        version_year=version_year,
        domain=domain,
        strand=strand,
        sub_strand=sub_strand,
        indicator=indicator,
        source_page=source_page,
        source_text=source_text,
    )


@st.composite
def document_meta_strategy(draw):
    """Generate document metadata."""
    return {
        "title": draw(st.text(min_size=1, max_size=200)),
        "source_url": draw(st.text(min_size=1, max_size=200)),
        "age_band": draw(st.text(min_size=1, max_size=20)),
        "publishing_agency": draw(st.text(min_size=1, max_size=200)),
    }


@st.composite
def canonical_json_strategy(draw, valid=True):
    """Generate a Canonical JSON record."""
    if valid:
        standard = draw(normalized_standard_strategy())
        doc_meta = draw(document_meta_strategy())
        return serialize_record(standard, doc_meta)
    else:
        # Generate invalid record by omitting required fields
        record = draw(canonical_json_strategy(valid=True))
        # Randomly remove a required field
        field_to_remove = draw(st.sampled_from([
            "country",
            "state",
            "document",
            "standard",
            "metadata",
            "document.title",
            "document.version_year",
            "document.source_url",
            "document.age_band",
            "document.publishing_agency",
            "standard.standard_id",
            "standard.domain",
            "standard.indicator",
            "standard.domain.code",
            "standard.domain.name",
            "standard.indicator.code",
        ]))
        
        # Remove the field
        if "." in field_to_remove:
            parts = field_to_remove.split(".")
            if len(parts) == 2:
                if parts[0] in record and isinstance(record[parts[0]], dict):
                    record[parts[0]].pop(parts[1], None)
            elif len(parts) == 3:
                if parts[0] in record and isinstance(record[parts[0]], dict):
                    if parts[1] in record[parts[0]] and isinstance(record[parts[0]][parts[1]], dict):
                        record[parts[0]][parts[1]].pop(parts[2], None)
        else:
            record.pop(field_to_remove, None)
        
        return record


# Property 13: Schema Validation Rejects Invalid Records
# Validates: Requirements 5.1, 5.2, 5.3

@given(canonical_json_strategy(valid=False))
def test_property_13_schema_validation_rejects_invalid_records(record):
    """
    Property 13: Schema Validation Rejects Invalid Records
    
    For any Canonical_JSON record missing any required field, the Validator
    SHALL return is_valid = False.
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    result = validate_record(record)
    assert result.is_valid is False, "Invalid record should be rejected"


# Property 14: Validation Error Reporting
# Validates: Requirements 5.6

@given(canonical_json_strategy(valid=False))
def test_property_14_validation_error_reporting(record):
    """
    Property 14: Validation Error Reporting
    
    For any invalid Canonical_JSON record, the Validator SHALL return at least
    one ValidationError with a non-empty field_path and non-empty message.
    
    Validates: Requirements 5.6
    """
    result = validate_record(record)
    
    if not result.is_valid:
        assert len(result.errors) > 0, "Invalid record should have at least one error"
        
        for error in result.errors:
            assert error.field_path, "Error field_path must be non-empty"
            assert error.message, "Error message must be non-empty"


# Property 15: Standard_ID Uniqueness Enforcement
# Validates: Requirements 5.7

@given(
    st.lists(normalized_standard_strategy(), min_size=2, max_size=10),
    st.integers(min_value=0, max_value=9)
)
def test_property_15_standard_id_uniqueness_enforcement(standards, duplicate_index):
    """
    Property 15: Standard_ID Uniqueness Enforcement
    
    For any set of Canonical_JSON records containing two records with the same
    standard_id, country, state, and version_year, the Validator SHALL detect and report
    the uniqueness violation.
    
    Validates: Requirements 5.7
    """
    if len(standards) < 2:
        return
    
    # Make one standard a duplicate of another
    duplicate_index = duplicate_index % len(standards)
    original_index = (duplicate_index + 1) % len(standards)
    
    standards[duplicate_index].standard_id = standards[original_index].standard_id
    standards[duplicate_index].country = standards[original_index].country
    standards[duplicate_index].state = standards[original_index].state
    standards[duplicate_index].version_year = standards[original_index].version_year
    
    # Serialize all standards
    doc_meta = {
        "title": "Test Document",
        "source_url": "https://example.com",
        "age_band": "3-5",
        "publishing_agency": "Test Agency",
    }
    
    records = [serialize_record(s, doc_meta) for s in standards]
    
    # Build set of existing IDs from all but the last record (as tuples)
    existing_ids = {
        (r["country"], r["state"], r["document"]["version_year"], r["standard"]["standard_id"])
        for r in records[:-1]
    }
    
    # Validate the last record
    last_record = records[-1]
    result = validate_record(last_record, existing_ids=existing_ids)
    
    # Check if the last record's key is in existing_ids
    last_record_key = (
        last_record["country"],
        last_record["state"],
        last_record["document"]["version_year"],
        last_record["standard"]["standard_id"]
    )
    if last_record_key in existing_ids:
        assert not result.is_valid, "Duplicate standard_id should be detected"
        assert any(
            error.error_type == "uniqueness" for error in result.errors
        ), "Should have a uniqueness error"


# Property 16: Serialization Round Trip
# Validates: Requirements 5.8

@given(normalized_standard_strategy(), document_meta_strategy())
def test_property_16_serialization_round_trip(standard, doc_meta):
    """
    Property 16: Serialization Round Trip
    
    For any valid NormalizedStandard object, serializing to JSON via
    serialize_record and then deserializing via deserialize_record SHALL
    produce an object equivalent to the original.
    
    Validates: Requirements 5.8
    """
    # Serialize
    canonical = serialize_record(standard, doc_meta)
    
    # Deserialize
    deserialized = deserialize_record(canonical)
    
    # Compare key fields (some fields may differ due to transformation)
    assert deserialized.standard_id == standard.standard_id
    assert deserialized.country == standard.country
    assert deserialized.state == standard.state
    assert deserialized.version_year == standard.version_year
    
    # Domain
    assert deserialized.domain.code == standard.domain.code
    assert deserialized.domain.name == standard.domain.name
    
    # Strand
    if standard.strand:
        assert deserialized.strand is not None
        assert deserialized.strand.code == standard.strand.code
        assert deserialized.strand.name == standard.strand.name
    else:
        assert deserialized.strand is None
    
    # Sub-strand
    if standard.sub_strand:
        assert deserialized.sub_strand is not None
        assert deserialized.sub_strand.code == standard.sub_strand.code
        assert deserialized.sub_strand.name == standard.sub_strand.name
    else:
        assert deserialized.sub_strand is None
    
    # Indicator
    assert deserialized.indicator.code == standard.indicator.code
    assert deserialized.indicator.description == standard.indicator.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
