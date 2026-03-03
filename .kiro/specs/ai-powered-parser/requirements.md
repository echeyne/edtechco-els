# Requirements Document

## Introduction

Replace the rule-based hierarchy parser in `src/els_pipeline/parser.py` with an AI-powered parser that uses Amazon Bedrock (Claude) to convert `DetectedElement` objects (output of `detector.py`) into `NormalizedStandard` objects. The current rule-based approach works for California and Arizona but fails for Texas because Texas uses Roman numeral domain codes with letter-based strand codes and age-prefixed indicator codes (e.g. `PK3.I.A.1`, `PK4.I.A.2`), which the prefix-matching and document-order strategies cannot resolve correctly.

## Glossary

- **Parser**: The `parse_hierarchy()` function and its supporting code in `src/els_pipeline/parser.py`.
- **Bedrock_Client**: The boto3 `bedrock-runtime` client used to invoke Claude via Amazon Bedrock.
- **DetectedElement**: A Pydantic model representing a single structural element detected by `detector.py` (fields: `level`, `code`, `title`, `description`, `confidence`, `source_page`, `source_text`, `needs_review`).
- **NormalizedStandard**: A Pydantic model representing a fully resolved standard with `domain`, `strand`, `sub_strand`, `indicator`, `standard_id`, `country`, `state`, `version_year`, `source_page`, `source_text`, and optional `age_band` fields.
- **ParseResult**: A Pydantic model returned by `parse_hierarchy()` containing `standards`, `indicators`, `orphaned_elements`, `status`, and `error`.
- **Age_Band**: A string parameter passed to `parse_hierarchy()` representing the target age group (e.g. `"PK3"`, `"PK4"`, `"36 months"`, `"48 months"`, `"PK"`). It does not need to be a specific month/year format. The LLM may detect a more specific age band from the indicator text; if so, that value is used instead of the parameter.
- **Standard_ID**: A deterministic identifier in the format `{COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`.
- **Orphaned_Element**: A `DetectedElement` that the Parser could not assign to a complete hierarchy (missing domain or indicator).

---

## Requirements

### Requirement 1: AI-Powered Hierarchy Parsing

**User Story:** As a pipeline engineer, I want the parser to use an LLM to resolve hierarchy relationships, so that documents with non-standard coding schemes (like Texas) are parsed correctly without hand-crafted rules.

#### Acceptance Criteria

1. WHEN `parse_hierarchy()` is called with a list of `DetectedElement` objects, THE Parser SHALL send those elements to the Bedrock_Client using the same invocation pattern as `detector.py` (model ID from `Config.BEDROCK_LLM_MODEL_ID`, region from `Config.AWS_REGION`).
2. WHEN the Bedrock_Client returns a response, THE Parser SHALL parse the JSON response into a list of `NormalizedStandard` objects.
3. WHEN the LLM response cannot be parsed as valid JSON, THE Parser SHALL retry the Bedrock call up to `MAX_PARSE_RETRIES` times before returning an error result.
4. WHEN the Bedrock_Client raises a `ClientError`, THE Parser SHALL retry the call up to `MAX_BEDROCK_RETRIES` times before returning an error result.
5. WHEN all retries are exhausted and parsing still fails, THE Parser SHALL return a `ParseResult` with `status="error"` and a descriptive `error` message.

---

### Requirement 2: Age Band on Indicators

**User Story:** As a data consumer, I want each indicator to carry an age band value, so that downstream systems can filter standards by the target age of a child.

#### Acceptance Criteria

1. WHEN the LLM identifies a more specific age band in an indicator's description or source text, THE Parser SHALL use that detected value as the `age_band` attribute on the corresponding `NormalizedStandard`.
2. WHEN no age band is found in the indicator's description or source text, THE Parser SHALL set the `age_band` attribute on the `NormalizedStandard` to the `age_band` parameter passed into `parse_hierarchy()`.
3. THE Parser SHALL accept `age_band` parameter values in any string format including `"PK3"`, `"PK4"`, `"36 months"`, `"48 months"`, and `"PK"`.

---

### Requirement 3: Public API

**User Story:** As a pipeline engineer, I want a clean, simple entry point for hierarchy parsing, so that callers have a single function to invoke.

#### Acceptance Criteria

1. THE Parser SHALL expose `parse_hierarchy(elements, country, state, version_year, age_band)` as the public entry point for hierarchy parsing.
2. THE Parser SHALL accept `age_band` as a keyword argument with a default value of `"PK"`.
3. WHEN `parse_hierarchy()` is called without the `age_band` argument, THE Parser SHALL use `"PK"` as the default age band.
4. THE Parser SHALL return a `ParseResult` object for all inputs, including error cases.

---

### Requirement 4: Preserved Standard ID Generation

**User Story:** As a data consumer, I want Standard IDs to remain deterministic and consistent, so that the same indicator always maps to the same ID regardless of how many times the pipeline runs.

#### Acceptance Criteria

1. THE Parser SHALL retain the `generate_standard_id(country, state, version_year, domain_code, indicator_code)` function with its existing signature and behavior.
2. WHEN `generate_standard_id()` is called with the same arguments, THE Parser SHALL return the same `Standard_ID` string every time.
3. THE Parser SHALL produce `Standard_ID` values in the format `{COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`.

---

### Requirement 5: Resilience and Error Handling

**User Story:** As a pipeline engineer, I want the parser to handle transient failures gracefully, so that a single bad LLM response or network hiccup does not fail the entire pipeline run.

#### Acceptance Criteria

1. WHEN a JSON parse error occurs on the LLM response, THE Parser SHALL log a warning and retry the Bedrock call with the same prompt.
2. WHEN a `ClientError` is raised by the Bedrock_Client, THE Parser SHALL log a warning and retry the call.
3. WHEN an unexpected exception occurs during parsing, THE Parser SHALL catch it, log the error, and return a `ParseResult` with `status="error"`.
4. IF the input `elements` list is empty, THEN THE Parser SHALL return a `ParseResult` with `status="error"` and an appropriate error message without calling the Bedrock_Client.
5. IF all input elements have `needs_review=True`, THEN THE Parser SHALL return a `ParseResult` with `status="error"` and an appropriate error message without calling the Bedrock_Client.

---

### Requirement 6: Removal of Rule-Based Logic

**User Story:** As a maintainer, I want the obsolete rule-based parsing functions removed, so that the codebase is simpler and there is no ambiguity about which parsing path is active.

#### Acceptance Criteria

1. THE Parser SHALL NOT contain the functions `detect_hierarchy_depth`, `normalize_hierarchy_mapping`, `assign_canonical_levels`, `_is_prefix_based`, `_find_parent_by_prefix`, `_build_standards_prefix`, or `_build_standards_doc_order` after the refactor.
2. THE Parser SHALL NOT use document-order or code-prefix matching to assign parent-child relationships between elements.
