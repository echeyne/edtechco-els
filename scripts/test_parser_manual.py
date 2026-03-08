#!/usr/bin/env python3
"""
Manual test script for hierarchy parser.

This script tests the hierarchy parser with sample detected elements from various states
and verifies Standard_ID format and uniqueness.

Usage:
    python scripts/test_parser_manual.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
from els_pipeline.models import DetectedElement, HierarchyLevelEnum
from els_pipeline.parser import parse_hierarchy, generate_standard_id


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_standard(standard, index):
    """Print a standard in a readable format."""
    print(f"\n  Standard #{index + 1}:")
    print(f"    Standard ID: {standard.standard_id}")
    print(f"    Country: {standard.country}")
    print(f"    State: {standard.state}")
    print(f"    Year: {standard.version_year}")
    print(f"    Domain: {standard.domain.code} - {standard.domain.name}")
    if standard.strand:
        print(f"    Strand: {standard.strand.code} - {standard.strand.name}")
    if standard.sub_strand:
        print(f"    Sub-strand: {standard.sub_strand.code} - {standard.sub_strand.name}")
    print(f"    Indicator: {standard.indicator.code} - {standard.indicator.name}")
    print(f"    Description: {standard.indicator.description}")
    print(f"    Source Page: {standard.source_page}")


def test_california_standards():
    """Test with California-style standards (4 levels) using real detector output."""
    print_section("Test 1: California Standards (4 levels) - Real Data")
    
    # Load real data from detector output
    detector_output_path = project_root / "detector_test_output.json"
    with open(detector_output_path, 'r') as f:
        detector_data = json.load(f)
    
    # Convert JSON elements to DetectedElement objects
    elements = []
    for elem in detector_data['elements']:
        elements.append(DetectedElement(
            level=HierarchyLevelEnum(elem['level']),
            code=elem['code'],
            title=elem['title'],
            description=elem['description'],
            confidence=elem['confidence'],
            source_page=elem['source_page'],
            source_text=elem['description'],  # Use description as source_text
            needs_review=elem['needs_review'],
        ))
    
    print(f"\n  Loaded {len(elements)} elements from detector_test_output.json")
    
    result = parse_hierarchy(elements, "US", "CA", 2021)
    
    print(f"\n  Status: {result.status}")
    print(f"  Total Standards: {len(result.standards)}")
    print(f"  Orphaned Elements: {len(result.orphaned_elements)}")
    
    if result.error:
        print(f"  Error: {result.error}")
    
    # Debug: Show element structure
    print("\n  Element Structure:")
    for elem in elements:
        print(f"    {elem.level.value}: {elem.code} - {elem.title}")
    
    for idx, standard in enumerate(result.standards):
        print_standard(standard, idx)
    
    if result.orphaned_elements:
        print("\n  Orphaned Elements:")
        for elem in result.orphaned_elements:
            print(f"    {elem.level.value}: {elem.code} - {elem.title}")
    
    # Verify Standard_ID format
    print("\n  Standard_ID Format Verification:")
    for standard in result.standards:
        expected_format = f"US-CA-2021-ATL-{standard.indicator.code}"
        matches = standard.standard_id == expected_format
        print(f"    {standard.standard_id} - {'✓ PASS' if matches else '✗ FAIL'}")
    
    # Verify uniqueness
    standard_ids = [s.standard_id for s in result.standards]
    unique_ids = set(standard_ids)
    print(f"\n  Uniqueness Check: {len(standard_ids)} total, {len(unique_ids)} unique - {'✓ PASS' if len(standard_ids) == len(unique_ids) else '✗ FAIL'}")


def test_texas_standards():
    """Test with Texas-style standards (3 levels)."""
    print_section("Test 2: Texas Standards (3 levels)")
    
    elements = [
        DetectedElement(
            level=HierarchyLevelEnum.DOMAIN,
            code="I",
            title="Social and Emotional Development",
            description="Social domain",
            confidence=0.95,
            source_page=10,
            source_text="Domain I text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.STRAND,
            code="I.A",
            title="Self-Concept",
            description="Self-concept strand",
            confidence=0.93,
            source_page=11,
            source_text="I.A strand text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR,
            code="I.A.1",
            title="Self-Awareness",
            description="Child demonstrates awareness of self as unique individual",
            confidence=0.90,
            source_page=12,
            source_text="I.A.1 indicator text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR,
            code="I.A.2",
            title="Self-Confidence",
            description="Child demonstrates confidence in own abilities",
            confidence=0.91,
            source_page=13,
            source_text="I.A.2 indicator text",
            needs_review=False,
        ),
    ]
    
    result = parse_hierarchy(elements, "US", "TX", 2020)
    
    print(f"\n  Status: {result.status}")
    print(f"  Total Standards: {len(result.standards)}")
    print(f"  Orphaned Elements: {len(result.orphaned_elements)}")
    
    for idx, standard in enumerate(result.standards):
        print_standard(standard, idx)
    
    # Verify depth normalization (3 levels = Domain + Strand + Indicator, no Sub-strand)
    print("\n  Depth Normalization Verification (3 levels):")
    for standard in result.standards:
        has_domain = standard.domain is not None
        has_strand = standard.strand is not None
        has_sub_strand = standard.sub_strand is None
        has_indicator = standard.indicator is not None
        
        all_correct = has_domain and has_strand and has_sub_strand and has_indicator
        print(f"    {standard.standard_id}: Domain={has_domain}, Strand={has_strand}, Sub-strand=None={has_sub_strand}, Indicator={has_indicator} - {'✓ PASS' if all_correct else '✗ FAIL'}")


def test_florida_standards():
    """Test with Florida-style standards (2 levels)."""
    print_section("Test 3: Florida Standards (2 levels)")
    
    elements = [
        DetectedElement(
            level=HierarchyLevelEnum.DOMAIN,
            code="PM",
            title="Physical and Motor Development",
            description="Physical domain",
            confidence=0.95,
            source_page=20,
            source_text="PM domain text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR,
            code="PM.1",
            title="Gross Motor Skills",
            description="Child demonstrates gross motor coordination",
            confidence=0.90,
            source_page=21,
            source_text="PM.1 indicator text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR,
            code="PM.2",
            title="Fine Motor Skills",
            description="Child demonstrates fine motor control",
            confidence=0.91,
            source_page=22,
            source_text="PM.2 indicator text",
            needs_review=False,
        ),
    ]
    
    result = parse_hierarchy(elements, "US", "FL", 2022)
    
    print(f"\n  Status: {result.status}")
    print(f"  Total Standards: {len(result.standards)}")
    print(f"  Orphaned Elements: {len(result.orphaned_elements)}")
    
    for idx, standard in enumerate(result.standards):
        print_standard(standard, idx)
    
    # Verify depth normalization (2 levels = Domain + Indicator, no Strand or Sub-strand)
    print("\n  Depth Normalization Verification (2 levels):")
    for standard in result.standards:
        has_domain = standard.domain is not None
        has_strand = standard.strand is None
        has_sub_strand = standard.sub_strand is None
        has_indicator = standard.indicator is not None
        
        all_correct = has_domain and has_strand and has_sub_strand and has_indicator
        print(f"    {standard.standard_id}: Domain={has_domain}, Strand=None={has_strand}, Sub-strand=None={has_sub_strand}, Indicator={has_indicator} - {'✓ PASS' if all_correct else '✗ FAIL'}")


def test_orphan_detection():
    """Test orphan detection."""
    print_section("Test 4: Orphan Detection")
    
    elements = [
        DetectedElement(
            level=HierarchyLevelEnum.DOMAIN,
            code="CD",
            title="Cognitive Development",
            description="Cognitive domain",
            confidence=0.95,
            source_page=30,
            source_text="CD domain text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR,
            code="CD.1",
            title="Valid Indicator",
            description="This indicator has a parent domain",
            confidence=0.90,
            source_page=31,
            source_text="CD.1 indicator text",
            needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR,
            code="ORPHAN.1",
            title="Orphaned Indicator",
            description="This indicator has no parent domain",
            confidence=0.90,
            source_page=32,
            source_text="ORPHAN.1 indicator text",
            needs_review=False,
        ),
    ]
    
    result = parse_hierarchy(elements, "US", "NY", 2021)
    
    print(f"\n  Status: {result.status}")
    print(f"  Total Standards: {len(result.standards)}")
    print(f"  Orphaned Elements: {len(result.orphaned_elements)}")
    
    print("\n  Valid Standards:")
    for idx, standard in enumerate(result.standards):
        print(f"    {idx + 1}. {standard.standard_id} - {standard.indicator.name}")
    
    print("\n  Orphaned Elements:")
    for idx, element in enumerate(result.orphaned_elements):
        print(f"    {idx + 1}. {element.code} - {element.title}")
    
    # Verify orphan detection
    orphan_codes = {e.code for e in result.orphaned_elements}
    standard_codes = {s.indicator.code for s in result.standards}
    
    print("\n  Orphan Detection Verification:")
    print(f"    Expected orphan: ORPHAN.1 - {'✓ PASS' if 'ORPHAN.1' in orphan_codes else '✗ FAIL'}")
    print(f"    Expected valid: CD.1 - {'✓ PASS' if 'CD.1' in standard_codes else '✗ FAIL'}")
    print(f"    No overlap: {'✓ PASS' if len(orphan_codes & standard_codes) == 0 else '✗ FAIL'}")


def test_standard_id_determinism():
    """Test Standard_ID determinism."""
    print_section("Test 5: Standard_ID Determinism")
    
    test_cases = [
        ("US", "CA", 2021, "LLD", "LLD.A.1.a"),
        ("US", "TX", 2020, "I", "I.A.1"),
        ("US", "FL", 2022, "PM", "PM.1"),
        ("US", "NY", 2021, "CD", "CD.1"),
    ]
    
    print("\n  Testing determinism (generating each ID twice):")
    for country, state, year, domain, indicator in test_cases:
        id1 = generate_standard_id(country, state, year, domain, indicator)
        id2 = generate_standard_id(country, state, year, domain, indicator)
        
        matches = id1 == id2
        expected_format = f"{country}-{state}-{year}-{domain}-{indicator}"
        format_matches = id1 == expected_format
        
        print(f"    {id1}")
        print(f"      Determinism: {'✓ PASS' if matches else '✗ FAIL'}")
        print(f"      Format: {'✓ PASS' if format_matches else '✗ FAIL'}")


def main():
    """Run all manual tests."""
    print("\n" + "=" * 80)
    print("  HIERARCHY PARSER MANUAL TEST SUITE")
    print("=" * 80)
    
    try:
        test_california_standards()
        test_texas_standards()
        test_florida_standards()
        test_orphan_detection()
        test_standard_id_determinism()
        
        print("\n" + "=" * 80)
        print("  ALL TESTS COMPLETED")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
