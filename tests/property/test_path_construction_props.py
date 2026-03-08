"""Property tests for S3 path construction.

Feature: els-normalization-pipeline
Property 1: S3 Path Construction
"""

import re
from hypothesis import given, strategies as st

from els_pipeline.ingester import construct_s3_path


# Strategy for generating valid country codes (2-letter uppercase ISO 3166-1 alpha-2)
country_code_strategy = st.text(
    alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    min_size=2,
    max_size=2
)

# Strategy for generating valid state codes (2-letter uppercase)
state_code_strategy = st.text(
    alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    min_size=2,
    max_size=2
)

# Strategy for generating version years
year_strategy = st.integers(min_value=2000, max_value=2030)

# Strategy for generating filenames
filename_strategy = st.text(
    alphabet=st.characters(blacklist_characters="/\\"),
    min_size=1,
    max_size=100
).filter(lambda x: x.strip() != "")


@given(
    country=country_code_strategy,
    state=state_code_strategy,
    year=year_strategy,
    filename=filename_strategy
)
def test_property_1_s3_path_construction(country: str, state: str, year: int, filename: str):
    """
    Property 1: S3 Path Construction
    
    For any valid country code, state code, version year, and filename, the constructed S3 key
    SHALL match the pattern {country}/{state}/{year}/{identifier} — no leading slashes,
    no double slashes, and all components present.
    
    Validates: Requirements 1.1, 5.5
    """
    # Construct the S3 path
    s3_path = construct_s3_path(country, state, year, filename)
    
    # Assert no leading slashes
    assert not s3_path.startswith("/"), f"S3 path should not start with '/': {s3_path}"
    
    # Assert no double slashes
    assert "//" not in s3_path, f"S3 path should not contain '//': {s3_path}"
    
    # Assert pattern matches {country}/{state}/{year}/{filename}
    pattern = r"^[^/]+/[^/]+/\d+/[^/]+$"
    assert re.match(pattern, s3_path), f"S3 path does not match expected pattern: {s3_path}"
    
    # Assert all components are present
    parts = s3_path.split("/")
    assert len(parts) == 4, f"S3 path should have exactly 4 components: {s3_path}"
    
    # Assert country component matches (after stripping)
    assert parts[0] == country.strip("/"), f"Country component mismatch: {parts[0]} != {country.strip('/')}"
    
    # Assert state component matches (after stripping)
    assert parts[1] == state.strip("/"), f"State component mismatch: {parts[1]} != {state.strip('/')}"
    
    # Assert year component matches
    assert parts[2] == str(year), f"Year component mismatch: {parts[2]} != {year}"
    
    # Assert filename component matches (after stripping)
    assert parts[3] == filename.strip("/"), f"Filename component mismatch: {parts[3]} != {filename.strip('/')}"
