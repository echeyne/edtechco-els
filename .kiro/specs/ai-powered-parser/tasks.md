# Implementation Plan: AI-Powered Parser

## Overview

Replace the rule-based parser in `src/els_pipeline/parser.py` with an LLM-powered implementation that calls Amazon Bedrock (Claude) to resolve hierarchy relationships between `DetectedElement` objects and produce `NormalizedStandard` objects.

## Tasks

- [x] 1. Add `age_band` field to `NormalizedStandard` model
  - Add `age_band: Optional[str] = None` to `NormalizedStandard` in `src/els_pipeline/models.py`
  - _Requirements: 2.1, 2.2_

- [x] 2. Implement the AI-powered parser
  - [x] 2.1 Write `build_parsing_prompt(elements, country, state, version_year, age_band) -> str`
    - Serialize the filtered `DetectedElement` list into a structured prompt
    - Instruct the LLM to output one JSON object per indicator with fields: `domain_code`, `domain_name`, `domain_description`, `strand_code`, `strand_name`, `strand_description`, `sub_strand_code`, `sub_strand_name`, `sub_strand_description`, `indicator_code`, `indicator_name`, `indicator_description`, `age_band`, `source_page`, `source_text`
    - Instruct the LLM to populate `domain_description`, `strand_description`, and `sub_strand_description` from the document text for each level; use `null` if no description exists
    - Include the `age_band` fallback instruction in the prompt
    - _Requirements: 1.1, 2.1, 2.2_

  - [x] 2.2 Write `call_bedrock_llm(prompt, max_retries=MAX_BEDROCK_RETRIES) -> str`
    - Mirror the implementation in `detector.py`: boto3 `bedrock-runtime` client, `Config.AWS_REGION`, `Config.BEDROCK_LLM_MODEL_ID`, retry on `ClientError`
    - _Requirements: 1.1, 1.4, 5.2_

  - [x] 2.3 Write `parse_llm_response(response_text, country, state, version_year, fallback_age_band) -> List[NormalizedStandard]`
    - Strip markdown fences, extract JSON array, validate required fields
    - Map `domain_description`, `strand_description`, and `sub_strand_description` from the LLM output onto the `description` field of the corresponding `HierarchyLevel` objects
    - Call `generate_standard_id()` for each indicator object
    - Apply `fallback_age_band` when the LLM returns `null` for `age_band`
    - Skip and log malformed objects rather than raising
    - _Requirements: 1.2, 2.1, 2.2, 4.1_

  - [x] 2.4 Write property test for `generate_standard_id` determinism and format
    - **Property 4: generate_standard_id determinism and format**
    - **Validates: Requirements 4.2, 4.3**
    - Use Hypothesis to generate arbitrary `(country, state, version_year, domain_code, indicator_code)` tuples; assert two calls return the same string matching the expected format
    - _Requirements: 4.2, 4.3_

  - [x] 2.5 Implement `parse_hierarchy(elements, country, state, version_year, age_band="PK") -> ParseResult`
    - Filter `needs_review=True` elements
    - Return `ParseResult(status="error")` immediately for empty or all-review inputs without calling Bedrock
    - Call `build_parsing_prompt`, then `call_bedrock_llm` with JSON-parse retry loop (up to `MAX_PARSE_RETRIES`)
    - Call `parse_llm_response` and build the final `ParseResult`
    - Wrap everything in a top-level `try/except` that returns `ParseResult(status="error")` on unexpected exceptions
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 3.4, 5.3, 5.4, 5.5_

  - [x] 2.6 Write property test: `parse_hierarchy` always returns `ParseResult`
    - **Property 1: parse_hierarchy always returns a ParseResult**
    - **Validates: Requirements 3.4, 5.3**
    - Use Hypothesis to generate arbitrary element lists (including empty, all-review, mixed); mock Bedrock; assert return type is always `ParseResult`
    - _Requirements: 3.4, 5.3_

  - [x] 2.7 Write property test: `age_band` fallback and passthrough
    - **Property 2: age_band fallback** and **Property 3: age_band passthrough**
    - **Validates: Requirements 2.2, 2.3, 3.2**
    - Use Hypothesis to generate arbitrary `age_band` strings; mock Bedrock to return `null` for `age_band`; assert the standard carries the parameter value and no exception is raised
    - _Requirements: 2.2, 2.3, 3.2_

- [x] 3. Remove rule-based functions
  - Delete `detect_hierarchy_depth`, `normalize_hierarchy_mapping`, `assign_canonical_levels`, `_is_prefix_based`, `_find_parent_by_prefix`, `_build_standards_prefix`, `_build_standards_doc_order` from `src/els_pipeline/parser.py`
  - _Requirements: 6.1, 6.2_

  - [x] 3.1 Write unit test: old functions are not exported
    - Assert that none of the removed function names exist in the `parser` module namespace
    - _Requirements: 6.1_

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update integration tests
  - [x] 5.1 Update `tests/integration/test_parser_integration.py` to mock Bedrock
    - Replace direct element-list assertions that relied on rule-based logic with mocked Bedrock responses
    - Add unit tests for: empty input, all-review input, JSON parse retry (verify call count), ClientError retry (verify call count)
    - _Requirements: 1.3, 1.4, 5.4, 5.5_

  - [x] 5.2 Write property tests for retry exhaustion
    - **Property 5: JSON parse retry exhaustion returns error**
    - **Property 6: ClientError retry exhaustion returns error**
    - **Validates: Requirements 1.3, 1.4, 1.5**
    - Mock Bedrock to always fail; assert `status="error"` and exact call count equals `MAX_PARSE_RETRIES + 1` or `MAX_BEDROCK_RETRIES + 1`
    - _Requirements: 1.3, 1.4, 1.5_

- [x] 6. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use Hypothesis (already in `pyproject.toml` dev dependencies); run with `pytest --hypothesis-seed=0` for reproducibility
- Mock boto3 using `unittest.mock.patch` or `moto` (already in dev dependencies)
- The `NormalizedStandard.age_band` field is `Optional[str]` — existing callers that don't pass `age_band` will get `None` or the default `"PK"` depending on LLM output
