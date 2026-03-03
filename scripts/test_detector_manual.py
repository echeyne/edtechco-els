#!/usr/bin/env python3
"""
Manual AWS test script for Structure Detector.

This script tests the structure detector with real AWS Bedrock on extracted text.

Prerequisites:
1. AWS credentials configured (via ~/.aws/credentials or environment variables)
2. Access to Amazon Bedrock with Claude model enabled
3. Extracted text blocks from a previous extraction step

Environment Variables:
- AWS_REGION: AWS region (default: us-east-1)
- BEDROCK_DETECTOR_LLM_MODEL_ID: Bedrock model ID (default: us.anthropic.claude-opus-4-6-v1)
- CONFIDENCE_THRESHOLD: Confidence threshold for review flagging (default: 0.8)

Usage:
    # Test with sample blocks:
    python scripts/test_detector_manual.py
    
    # Test with extraction file:
    python scripts/test_detector_manual.py extraction_sample.json
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.els_pipeline.detector import detect_structure
from src.els_pipeline.models import TextBlock

# Configure logging to see detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def load_extraction_data(filepath: str) -> list[TextBlock]:
    """Load extraction data and convert to TextBlock objects."""
    logger.info(f"Loading extraction data from {filepath}")
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    blocks = []
    for block_data in data['blocks']:
        block = TextBlock(
            text=block_data['text'],
            page_number=block_data['page_number'],
            block_type=block_data['block_type'],
            confidence=block_data['confidence'],
            geometry=block_data.get('geometry', {}),
            row_index=block_data.get('row_index'),
            col_index=block_data.get('col_index')
        )
        blocks.append(block)
    
    logger.info(f"Loaded {len(blocks)} text blocks")
    return blocks


def create_sample_text_blocks():
    """
    Create sample text blocks for testing.
    
    These blocks are from page 4 of the actual California early learning standards document,
    extracted using AWS Textract.
    """
    return [
        TextBlock(
            text="Approaches",
            page_number=4,
            block_type="LINE",
            confidence=0.99990234375,
            geometry={"BoundingBox": {"Top": 0.1, "Left": 0.1, "Width": 0.3, "Height": 0.02}}
        ),
        TextBlock(
            text="California Preschool/Transitional Kindergarten Learning Foundations",
            page_number=4,
            block_type="LINE",
            confidence=0.936014404296875,
            geometry={"BoundingBox": {"Top": 0.12, "Left": 0.1, "Width": 0.8, "Height": 0.02}}
        ),
        TextBlock(
            text="to Learning",
            page_number=4,
            block_type="LINE",
            confidence=0.99970703125,
            geometry={"BoundingBox": {"Top": 0.14, "Left": 0.1, "Width": 0.3, "Height": 0.02}}
        ),
        TextBlock(
            text="Approaches to Learning",
            page_number=4,
            block_type="LINE",
            confidence=0.9998345947265626,
            geometry={"BoundingBox": {"Top": 0.2, "Left": 0.1, "Width": 0.6, "Height": 0.02}}
        ),
        TextBlock(
            text="Strand: 1.0 — Motivation to Learn",
            page_number=4,
            block_type="LINE",
            confidence=0.9561592864990235,
            geometry={"BoundingBox": {"Top": 0.25, "Left": 0.1, "Width": 0.6, "Height": 0.02}}
        ),
        TextBlock(
            text="Sub-Strand — Curiosity and Interest",
            page_number=4,
            block_type="LINE",
            confidence=0.9110407257080078,
            geometry={"BoundingBox": {"Top": 0.28, "Left": 0.1, "Width": 0.6, "Height": 0.02}}
        ),
        TextBlock(
            text="Foundation 1.1 Curiosity and Interest",
            page_number=4,
            block_type="LINE",
            confidence=0.9992140197753906,
            geometry={"BoundingBox": {"Top": 0.31, "Left": 0.1, "Width": 0.6, "Height": 0.02}}
        ),
        TextBlock(
            text="Early (3 to 4 ½ Years)",
            page_number=4,
            block_type="LINE",
            confidence=0.8596340942382813,
            geometry={"BoundingBox": {"Top": 0.35, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Later (4 to 5 ½ Years)",
            page_number=4,
            block_type="LINE",
            confidence=0.9269058990478516,
            geometry={"BoundingBox": {"Top": 0.35, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Express interest in some familiar and new",
            page_number=4,
            block_type="LINE",
            confidence=0.9995897674560547,
            geometry={"BoundingBox": {"Top": 0.38, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Express interest in a broader range of familiar",
            page_number=4,
            block_type="LINE",
            confidence=0.9990084838867187,
            geometry={"BoundingBox": {"Top": 0.38, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="objects, people, and activities in their",
            page_number=4,
            block_type="LINE",
            confidence=0.999753189086914,
            geometry={"BoundingBox": {"Top": 0.4, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="and new objects, people, and activities by",
            page_number=4,
            block_type="LINE",
            confidence=0.9998732757568359,
            geometry={"BoundingBox": {"Top": 0.4, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="immediate environment. Seek information by",
            page_number=4,
            block_type="LINE",
            confidence=0.9996615600585937,
            geometry={"BoundingBox": {"Top": 0.42, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="exploring more extensively with their senses,",
            page_number=4,
            block_type="LINE",
            confidence=0.999951171875,
            geometry={"BoundingBox": {"Top": 0.42, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="exploring with their senses, describing their",
            page_number=4,
            block_type="LINE",
            confidence=0.9999837493896484,
            geometry={"BoundingBox": {"Top": 0.44, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="describing their observations in greater detail,",
            page_number=4,
            block_type="LINE",
            confidence=0.9996854400634766,
            geometry={"BoundingBox": {"Top": 0.44, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="observations, and asking simple questions.",
            page_number=4,
            block_type="LINE",
            confidence=0.9993638610839843,
            geometry={"BoundingBox": {"Top": 0.46, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="and asking more detailed questions.",
            page_number=4,
            block_type="LINE",
            confidence=0.9998812103271484,
            geometry={"BoundingBox": {"Top": 0.46, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Sub-Strand - Initiative",
            page_number=4,
            block_type="LINE",
            confidence=0.8612835693359375,
            geometry={"BoundingBox": {"Top": 0.5, "Left": 0.1, "Width": 0.5, "Height": 0.02}}
        ),
        TextBlock(
            text="Foundation 1.2 Initiative",
            page_number=4,
            block_type="LINE",
            confidence=0.9988553619384766,
            geometry={"BoundingBox": {"Top": 0.53, "Left": 0.1, "Width": 0.5, "Height": 0.02}}
        ),
        TextBlock(
            text="Early (3 to 4 ½ Years)",
            page_number=4,
            block_type="LINE",
            confidence=0.8603997039794922,
            geometry={"BoundingBox": {"Top": 0.56, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Later (4 to 5 1/2 Years)",
            page_number=4,
            block_type="LINE",
            confidence=0.9271650695800782,
            geometry={"BoundingBox": {"Top": 0.56, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Demonstrate initiative by starting activities",
            page_number=4,
            block_type="LINE",
            confidence=0.9990238189697266,
            geometry={"BoundingBox": {"Top": 0.59, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Demonstrate initiative by starting activities",
            page_number=4,
            block_type="LINE",
            confidence=0.9993427276611329,
            geometry={"BoundingBox": {"Top": 0.59, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="(such as simple play scenarios), initiating",
            page_number=4,
            block_type="LINE",
            confidence=0.9993058013916015,
            geometry={"BoundingBox": {"Top": 0.61, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="(such as detailed and more complex play",
            page_number=4,
            block_type="LINE",
            confidence=0.9997884368896485,
            geometry={"BoundingBox": {"Top": 0.61, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="social interactions (such as helping others),",
            page_number=4,
            block_type="LINE",
            confidence=0.9996881103515625,
            geometry={"BoundingBox": {"Top": 0.63, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="scenarios), initiating social interactions (such",
            page_number=4,
            block_type="LINE",
            confidence=0.9995835113525391,
            geometry={"BoundingBox": {"Top": 0.63, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="and seeking solutions to problems.",
            page_number=4,
            block_type="LINE",
            confidence=0.9998014831542968,
            geometry={"BoundingBox": {"Top": 0.65, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="as helping others) more often, and seeking",
            page_number=4,
            block_type="LINE",
            confidence=0.9997895812988281,
            geometry={"BoundingBox": {"Top": 0.65, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="solutions to problems more persistently.",
            page_number=4,
            block_type="LINE",
            confidence=0.9996826934814453,
            geometry={"BoundingBox": {"Top": 0.67, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Sub-Strand — Engagement",
            page_number=4,
            block_type="LINE",
            confidence=0.8434334564208984,
            geometry={"BoundingBox": {"Top": 0.71, "Left": 0.1, "Width": 0.5, "Height": 0.02}}
        ),
        TextBlock(
            text="Foundation 1.3 Engagement",
            page_number=4,
            block_type="LINE",
            confidence=0.9992459869384765,
            geometry={"BoundingBox": {"Top": 0.74, "Left": 0.1, "Width": 0.5, "Height": 0.02}}
        ),
        TextBlock(
            text="Early (3 to 4 1/2 Years)",
            page_number=4,
            block_type="LINE",
            confidence=0.8591716766357422,
            geometry={"BoundingBox": {"Top": 0.77, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Later (4 to 5 1/2 Years)",
            page_number=4,
            block_type="LINE",
            confidence=0.9296955108642578,
            geometry={"BoundingBox": {"Top": 0.77, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Actively engage by focusing and concentrating",
            page_number=4,
            block_type="LINE",
            confidence=0.9998020172119141,
            geometry={"BoundingBox": {"Top": 0.8, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="Actively engage by focusing and concentrating",
            page_number=4,
            block_type="LINE",
            confidence=0.9998847198486328,
            geometry={"BoundingBox": {"Top": 0.8, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="on activities for brief periods of time with",
            page_number=4,
            block_type="LINE",
            confidence=0.9998271179199218,
            geometry={"BoundingBox": {"Top": 0.82, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="on activities for longer periods of time with",
            page_number=4,
            block_type="LINE",
            confidence=0.9997030639648438,
            geometry={"BoundingBox": {"Top": 0.82, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="adult support.",
            page_number=4,
            block_type="LINE",
            confidence=0.999951171875,
            geometry={"BoundingBox": {"Top": 0.84, "Left": 0.1, "Width": 0.4, "Height": 0.02}}
        ),
        TextBlock(
            text="less adult support.",
            page_number=4,
            block_type="LINE",
            confidence=0.9999349212646484,
            geometry={"BoundingBox": {"Top": 0.84, "Left": 0.55, "Width": 0.4, "Height": 0.02}}
        ),
    ]


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_element(element, index):
    """Print a detected element in a formatted way."""
    print(f"\n  Element {index + 1}:")
    print(f"    Level:       {element.level}")
    print(f"    Code:        {element.code}")
    print(f"    Title:       {element.title}")
    print(f"    Description: {element.description[:100]}..." if len(element.description) > 100 else f"    Description: {element.description}")
    print(f"    Confidence:  {element.confidence:.2f}")
    print(f"    Page:        {element.source_page}")
    print(f"    Needs Review: {element.needs_review}")


def main():
    """Run the manual test."""
    print_section("Structure Detector Manual AWS Test")
    
    # Check environment
    print("\nEnvironment Configuration:")
    print(f"  AWS_REGION:            {os.getenv('AWS_REGION', 'us-east-1')}")
    print(f"  BEDROCK_DETECTOR_LLM_MODEL_ID:  {os.getenv('BEDROCK_DETECTOR_LLM_MODEL_ID', 'us.anthropic.claude-sonnet-4-6')}")
    print(f"  CONFIDENCE_THRESHOLD:  {os.getenv('CONFIDENCE_THRESHOLD', '0.7')}")
    
    # Determine if we're loading from file or using sample blocks
    if len(sys.argv) > 1:
        extraction_file = sys.argv[1]
        if not Path(extraction_file).exists():
            logger.error(f"File not found: {extraction_file}")
            logger.info("Please provide a valid extraction file path")
            return 1
        
        print_section("Loading Extraction Data from File")
        print(f"\n  Loading from: {extraction_file}")
        text_blocks = load_extraction_data(extraction_file)
        print(f"  Loaded {len(text_blocks)} text blocks")
    else:
        # Create sample text blocks
        print_section("Creating Sample Text Blocks")
        text_blocks = create_sample_text_blocks()
        print(f"\n  Created {len(text_blocks)} text blocks from page 4 of the actual document")
        print(f"  (Extracted using AWS Textract from California Preschool/TK Learning Foundations)")
    
    # Run structure detection
    print_section("Running Structure Detection")
    print("\n  Calling Amazon Bedrock to detect hierarchical structure...")
    print("  This may take 10-30 seconds depending on the model and text length.")
    
    try:
        result = detect_structure(
            blocks=text_blocks,
            document_s3_key="test/california-standards-sample.pdf"
        )
        
        # Display results
        print_section("Detection Results")
        
        print(f"\n  Status:        {result.status}")
        print(f"  Document:      {result.document_s3_key}")
        print(f"  Elements:      {len(result.elements)}")
        print(f"  Review Count:  {result.review_count}")
        
        if result.error:
            print(f"  Error:         {result.error}")
        
        # Display detected elements
        if result.elements:
            print_section("Detected Elements")
            
            # Show first 20 elements in detail
            display_count = min(20, len(result.elements))
            for idx in range(display_count):
                print_element(result.elements[idx], idx)
            
            if len(result.elements) > display_count:
                print(f"\n  ... and {len(result.elements) - display_count} more elements")
                print("\n  Additional elements (summary):")
                for idx in range(display_count, len(result.elements)):
                    elem = result.elements[idx]
                    print(f"    {idx + 1}. [{elem.level.value}] {elem.code} - {elem.title[:50]} (conf: {elem.confidence:.2f})")
            
            # Summary by level
            print_section("Summary by Hierarchy Level")
            
            level_counts = {}
            for element in result.elements:
                level = element.level.value
                level_counts[level] = level_counts.get(level, 0) + 1
            
            for level in ['domain', 'strand', 'sub_strand', 'indicator']:
                count = level_counts.get(level, 0)
                print(f"  {level.capitalize():12} {count:3d}")
            
            # Elements needing review
            if result.review_count > 0:
                print_section("Elements Needing Review")
                
                review_elements = [e for e in result.elements if e.needs_review]
                for idx, element in enumerate(review_elements):
                    print_element(element, idx)
        
        # Save results to file
        output_file = Path(__file__).parent.parent / "detector_test_output.json"
        with open(output_file, 'w') as f:
            json.dump({
                'status': result.status,
                'document_s3_key': result.document_s3_key,
                'total_elements': len(result.elements),
                'review_count': result.review_count,
                'error': result.error,
                'elements': [
                    {
                        'level': e.level.value,
                        'code': e.code,
                        'title': e.title,
                        'description': e.description,
                        'confidence': e.confidence,
                        'source_page': e.source_page,
                        'needs_review': e.needs_review
                    }
                    for e in result.elements
                ]
            }, f, indent=2)
        
        print_section("Test Complete")
        print(f"\n  Results saved to: {output_file}")
        print("\n  ✓ Structure detection completed successfully!")
        
        if result.status == "success":
            return 0
        else:
            return 1
            
    except Exception as e:
        print_section("Test Failed")
        print(f"\n  Error: {e}")
        print("\n  Common issues:")
        print("    - AWS credentials not configured")
        print("    - Bedrock model not enabled in your AWS account")
        print("    - Insufficient IAM permissions for bedrock:InvokeModel")
        print("    - Network connectivity issues")
        print("\n  Please check your AWS configuration and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
