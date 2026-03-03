"""AI-powered hierarchy parser for ELS pipeline.

Uses Amazon Bedrock (Claude) to resolve parent-child relationships between
DetectedElement objects and produce NormalizedStandard objects. Replaces the
previous rule-based prefix-matching and document-order strategies.
"""

import json
import logging
import re
from typing import List, Dict, Any

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError

from .models import (
    DetectedElement,
    NormalizedStandard,
    ParseResult,
    HierarchyLevel,
    StatusEnum,
)
from .config import Config

logger = logging.getLogger(__name__)

# Constants
MAX_PARSE_RETRIES = 2
MAX_BEDROCK_RETRIES = 2
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 64000


def generate_standard_id(
    country: str, state: str, version_year: int, domain_code: str, indicator_code: str
) -> str:
    """
    Generate a deterministic Standard_ID.

    Returns:
        Standard_ID in format: {COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}
    """
    return f"{country}-{state}-{version_year}-{domain_code}-{indicator_code}"


def build_parsing_prompt(
    elements: List[DetectedElement],
    country: str,
    state: str,
    version_year: int,
    age_band: str,
) -> str:
    """
    Serialize DetectedElement objects into a structured prompt for the LLM.

    Instructs the LLM to output one JSON object per indicator with full
    hierarchy context including descriptions for each level.

    Args:
        elements: Filtered list of DetectedElement objects (needs_review=False)
        country: Two-letter country code
        state: State abbreviation
        version_year: Version year of the standards document
        age_band: Default age band to use when the LLM cannot detect one

    Returns:
        Prompt string ready to send to Bedrock
    """
    serialized = []
    for el in elements:
        serialized.append({
            "level": el.level.value,
            "code": el.code,
            "title": el.title,
            "description": el.description,
            "source_page": el.source_page,
            "source_text": el.source_text,
        })

    elements_json = json.dumps(serialized, indent=2)

    prompt = f"""You are an expert at analyzing early learning standards documents. You will be given a list of detected structural elements from a {country}-{state} ({version_year}) standards document. Each element has a level (domain, strand, sub_strand, or indicator), a code, a title, a description, and source information.

Your task is to resolve the hierarchy: assign each indicator to its correct domain, strand, and sub_strand based on the document's structural context and coding scheme.

Here are the detected elements:

{elements_json}

Return a JSON array where each object represents one indicator with its full hierarchy. Use this exact schema for each object:

{{
  "domain_code": "string",
  "domain_name": "string",
  "domain_description": "string or null",
  "strand_code": "string or null",
  "strand_name": "string or null",
  "strand_description": "string or null",
  "sub_strand_code": "string or null",
  "sub_strand_name": "string or null",
  "sub_strand_description": "string or null",
  "indicator_code": "string",
  "indicator_name": "string",
  "indicator_description": "string or null",
  "age_band": "string or null",
  "source_page": integer,
  "source_text": "string"
}}

Rules:
- Populate domain_description, strand_description, and sub_strand_description from the document text (the description field of the corresponding element). Use null if no description exists for that level.
- If a hierarchy level does not exist (e.g. no sub_strand), set its code, name, and description to null.
- For age_band: examine each indicator's code, title, description, and source_text for age-related information (e.g. "PK3", "PK4", "36 months", "48 months", "3-4 1/2 years). If you detect a specific age band, use that value. If no age band is detectable, set age_band to null. The caller will apply the default age band "{age_band}" for any null values.
- Return ONLY the JSON array, no other text.
- Every indicator element must appear exactly once in the output."""

    return prompt


def call_bedrock_llm(prompt: str, max_retries: int = MAX_BEDROCK_RETRIES) -> str:
    """
    Call Amazon Bedrock LLM with the given prompt.

    Mirrors the implementation in detector.py: boto3 bedrock-runtime client,
    Config.AWS_REGION, Config.BEDROCK_LLM_MODEL_ID, retry on ClientError.

    Args:
        prompt: The prompt to send to the LLM
        max_retries: Maximum number of retry attempts

    Returns:
        LLM response text

    Raises:
        ClientError: If Bedrock API call fails after all retries
        ValueError: If response format is unexpected
    """
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=Config.AWS_REGION,
        config=BotocoreConfig(
            read_timeout=300,
            connect_timeout=10,
            retries={"max_attempts": 0},
        ),
    )

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": LLM_TEMPERATURE,
    }

    logger.info(f"Calling Bedrock with model: {Config.BEDROCK_LLM_MODEL_ID}")

    for attempt in range(max_retries + 1):
        try:
            response = bedrock.invoke_model(
                modelId=Config.BEDROCK_PARSER_LLM_MODEL_ID,
                body=json.dumps(request_body),
            )
            response_body = json.loads(response["body"].read())

            if "content" not in response_body or len(response_body["content"]) == 0:
                raise ValueError("Unexpected response format from Bedrock: missing content")

            response_text = response_body["content"][0]["text"]
            logger.info(f"Bedrock response received: {len(response_text)} characters")
            return response_text

        except ClientError as e:
            if attempt < max_retries:
                logger.warning(
                    f"Bedrock API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                continue
            else:
                logger.error(
                    f"Bedrock API call failed after {max_retries + 1} attempts: {e}"
                )
                raise

    raise RuntimeError("Failed to get response from Bedrock after all retries")


def parse_llm_response(
    response_text: str,
    country: str,
    state: str,
    version_year: int,
    fallback_age_band: str,
) -> List[NormalizedStandard]:
    """
    Parse the LLM JSON response into NormalizedStandard objects.

    Strips markdown fences, extracts the JSON array, validates required fields,
    maps descriptions onto HierarchyLevel objects, generates standard IDs, and
    applies the fallback age_band when the LLM returns null.

    Args:
        response_text: Raw text response from the LLM
        country: Two-letter country code
        state: State abbreviation
        version_year: Version year
        fallback_age_band: Age band to use when the LLM returns null

    Returns:
        List of NormalizedStandard objects

    Raises:
        ValueError: If no valid JSON array can be extracted
    """
    text = response_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines[1:] if not line.strip().startswith("```")
        ).strip()

    # Find JSON array boundaries
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        raise ValueError("No valid JSON array found in LLM response")

    data = json.loads(text[start_idx : end_idx + 1])

    required_fields = {"domain_code", "domain_name", "indicator_code", "indicator_name"}
    standards: List[NormalizedStandard] = []

    for obj in data:
        if not isinstance(obj, dict):
            logger.warning(f"Skipping non-dict item in LLM response: {obj}")
            continue

        missing = required_fields - obj.keys()
        if missing:
            logger.warning(f"Skipping malformed object, missing fields {missing}: {obj}")
            continue

        try:
            domain = HierarchyLevel(
                code=obj["domain_code"],
                name=obj["domain_name"],
                description=obj.get("domain_description"),
            )

            strand = None
            if obj.get("strand_code") and obj.get("strand_name"):
                strand = HierarchyLevel(
                    code=obj["strand_code"],
                    name=obj["strand_name"],
                    description=obj.get("strand_description"),
                )

            sub_strand = None
            if obj.get("sub_strand_code") and obj.get("sub_strand_name"):
                sub_strand = HierarchyLevel(
                    code=obj["sub_strand_code"],
                    name=obj["sub_strand_name"],
                    description=obj.get("sub_strand_description"),
                )

            indicator = HierarchyLevel(
                code=obj["indicator_code"],
                name=obj["indicator_name"],
                description=obj.get("indicator_description"),
            )

            age_band = obj.get("age_band") or fallback_age_band

            standard_id = generate_standard_id(
                country, state, version_year, obj["domain_code"], obj["indicator_code"]
            )

            source_page = obj.get("source_page", 1)
            source_text = obj.get("source_text", "")

            standards.append(
                NormalizedStandard(
                    standard_id=standard_id,
                    country=country,
                    state=state,
                    version_year=version_year,
                    domain=domain,
                    strand=strand,
                    sub_strand=sub_strand,
                    indicator=indicator,
                    age_band=age_band,
                    source_page=source_page,
                    source_text=source_text,
                )
            )
        except Exception as e:
            logger.warning(f"Skipping object due to validation error: {e} — {obj}")
            continue

    return standards


def parse_hierarchy(
    elements: List[DetectedElement],
    country: str,
    state: str,
    version_year: int,
    age_band: str = "PK",
) -> ParseResult:
    """
    Parse detected elements into normalized standards using an LLM.

    Filters out needs_review elements, validates the remaining list, then
    delegates hierarchy resolution to Amazon Bedrock (Claude).

    Args:
        elements: List of DetectedElement objects from the detector
        country: Two-letter country code
        state: State abbreviation
        version_year: Version year of the standards document
        age_band: Default age band (default: "PK")

    Returns:
        ParseResult with standards, indicators, orphaned elements, and status
    """
    try:
        # Filter out elements flagged for review
        valid_elements = [e for e in elements if not e.needs_review]

        if not valid_elements:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=elements,
                status=StatusEnum.ERROR.value,
                error="No valid elements to parse (all flagged for review or empty input)",
            )

        # Build prompt and call LLM with JSON-parse retry loop
        prompt = build_parsing_prompt(
            valid_elements, country, state, version_year, age_band
        )

        for parse_attempt in range(MAX_PARSE_RETRIES + 1):
            try:
                response_text = call_bedrock_llm(prompt)
                standards = parse_llm_response(
                    response_text, country, state, version_year, age_band
                )
                break
            except (ValueError, json.JSONDecodeError) as e:
                if parse_attempt < MAX_PARSE_RETRIES:
                    logger.warning(
                        f"JSON parse failed (attempt {parse_attempt + 1}/{MAX_PARSE_RETRIES + 1}): {e}"
                    )
                    continue
                else:
                    logger.error(
                        f"JSON parse failed after {MAX_PARSE_RETRIES + 1} attempts: {e}"
                    )
                    return ParseResult(
                        standards=[],
                        indicators=[],
                        orphaned_elements=elements,
                        status=StatusEnum.ERROR.value,
                        error=f"Failed to parse LLM response after {MAX_PARSE_RETRIES + 1} attempts: {e}",
                    )

        return ParseResult(
            standards=standards,
            indicators=[s.model_dump() for s in standards],
            orphaned_elements=[],
            status=StatusEnum.SUCCESS.value,
            error=None,
        )

    except Exception as e:
        logger.error(f"Unexpected error in parse_hierarchy: {e}")
        return ParseResult(
            standards=[],
            indicators=[],
            orphaned_elements=elements,
            status=StatusEnum.ERROR.value,
            error=f"Parsing failed: {str(e)}",
        )
