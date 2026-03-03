"""Local test script for parser.py using detector_texas_test_output.json.

Usage:
    python test_parser_local.py

Requires AWS credentials configured (e.g. via ~/.aws/credentials or env vars).
Loads .env.dev for config overrides.
"""

import json
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env.dev before importing pipeline modules so Config picks up overrides
load_dotenv(".env.dev")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from els_pipeline.models import DetectedElement
from els_pipeline.parser import (
    build_parsing_prompt,
    call_bedrock_llm,
    parse_llm_response,
    parse_hierarchy,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_detector_output(path: str = "detector_texas_test_output.json") -> list[DetectedElement]:
    """Load detector output JSON and convert to DetectedElement instances."""
    with open(path) as f:
        data = json.load(f)

    elements = [DetectedElement(**el) for el in data["elements"]]
    logger.info(f"Loaded {len(elements)} elements from {path}")
    return elements


def test_prompt_only():
    """Just build and print the prompt — no Bedrock call."""
    elements = load_detector_output()
    prompt = build_parsing_prompt(elements, "US", "TX", 2024, "PK")
    logger.info(f"Prompt length: {len(prompt)} chars")
    print("\n--- PROMPT (first 2000 chars) ---")
    print(prompt[:2000])
    print("...")
    return prompt


def test_full_pipeline():
    """Run the full parse_hierarchy flow against Bedrock."""
    elements = load_detector_output()
    logger.info("Calling parse_hierarchy (this will hit Bedrock)...")

    result = parse_hierarchy(
        elements=elements,
        country="US",
        state="TX",
        version_year=2024,
        age_band="PK",
    )

    logger.info(f"Status: {result.status}")
    logger.info(f"Standards returned: {len(result.standards)}")
    logger.info(f"Orphaned elements: {len(result.orphaned_elements)}")

    if result.error:
        logger.error(f"Error: {result.error}")

    if result.standards:
        # Save output for inspection
        output = {
            "status": result.status,
            "total_standards": len(result.standards),
            "standards": [s.model_dump() for s in result.standards],
        }
        out_path = "parser_texas_local_output.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Output saved to {out_path}")

        # Print a sample
        print("\n--- FIRST STANDARD ---")
        print(json.dumps(result.standards[0].model_dump(), indent=2))

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Local parser test")
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Only build the prompt, don't call Bedrock",
    )
    args = parser.parse_args()

    if args.prompt_only:
        test_prompt_only()
    else:
        test_full_pipeline()
