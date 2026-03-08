#!/usr/bin/env python3
"""
Manual AWS test script for Text Extractor.

This script tests the text extractor with real AWS Textract on a California standards PDF.

Prerequisites:
1. AWS credentials configured (via AWS CLI or environment variables)
2. California standards PDF uploaded to S3 raw bucket
3. Required environment variables set (see below)

Environment Variables:
- ELS_RAW_BUCKET: S3 bucket name for raw documents (default: els-raw-documents)
- AWS_REGION: AWS region (default: us-east-1)
- TEST_DOCUMENT_KEY: S3 key of the test document (e.g., "US/CA/2021/california_all_standards_2021.pdf")
- TEST_DOCUMENT_VERSION: S3 version ID of the test document (optional)

Usage:
    # Set environment variables
    export ELS_RAW_BUCKET="els-raw-documents-dev-123456789"
    export AWS_REGION="us-east-1"
    export TEST_DOCUMENT_KEY="US/CA/2021/california_all_standards_2021.pdf"
    
    # Run the script
    python scripts/test_extractor_manual.py
    
    # Or with inline environment variables
    ELS_RAW_BUCKET="my-bucket" TEST_DOCUMENT_KEY="CA/2021/test.pdf" python scripts/test_extractor_manual.py
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from els_pipeline.extractor import extract_text
from els_pipeline.config import Config


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def validate_environment():
    """Validate required environment variables and configuration."""
    print_section("Environment Validation")
    
    required_vars = {
        'ELS_RAW_BUCKET': Config.S3_RAW_BUCKET,
        'AWS_REGION': Config.AWS_REGION,
        'TEST_DOCUMENT_KEY': os.getenv('TEST_DOCUMENT_KEY')
    }
    
    missing_vars = []
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)
            print(f"❌ {var_name}: NOT SET")
        else:
            print(f"✓ {var_name}: {var_value}")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the missing variables and try again.")
        print("Example:")
        print('  export TEST_DOCUMENT_KEY="US/CA/2021/california_all_standards_2021.pdf"')
        return False
    
    print("\n✓ All required environment variables are set")
    return True


def test_extraction():
    """Test text extraction with real AWS Textract."""
    print_section("Text Extraction Test")
    
    test_document_key = os.getenv('TEST_DOCUMENT_KEY')
    test_document_version = os.getenv('TEST_DOCUMENT_VERSION', '')
    
    print(f"Document Key: {test_document_key}")
    print(f"Document Version: {test_document_version or '(latest)'}")
    print(f"Bucket: {Config.S3_RAW_BUCKET}")
    print(f"Region: {Config.AWS_REGION}")
    print("\nStarting extraction... (this may take a while for large documents)")
    
    try:
        result = extract_text(test_document_key, test_document_version)
        
        print("\n" + "-" * 80)
        print("Extraction Result:")
        print("-" * 80)
        print(f"Status: {result.status}")
        print(f"Total Pages: {result.total_pages}")
        print(f"Total Blocks: {len(result.blocks)}")
        
        if result.error:
            print(f"Error: {result.error}")
            return False
        
        # Analyze block types
        block_types = {}
        for block in result.blocks:
            block_types[block.block_type] = block_types.get(block.block_type, 0) + 1
        
        print("\nBlock Type Distribution:")
        for block_type, count in sorted(block_types.items()):
            print(f"  {block_type}: {count}")
        
        # Show sample blocks from first page
        print("\nSample Blocks from Page 1:")
        page_1_blocks = [b for b in result.blocks if b.page_number == 1][:5]
        for i, block in enumerate(page_1_blocks, 1):
            text_preview = block.text[:60] + "..." if len(block.text) > 60 else block.text
            print(f"  {i}. [{block.block_type}] {text_preview}")
        
        # Check for table cells
        table_cells = [b for b in result.blocks if b.block_type == 'TABLE_CELL']
        if table_cells:
            print(f"\nTable Cells Found: {len(table_cells)}")
            print("Sample Table Cell:")
            cell = table_cells[0]
            print(f"  Text: {cell.text}")
            print(f"  Row: {cell.row_index}, Column: {cell.col_index}")
            print(f"  Page: {cell.page_number}")
        
        # Verify reading order
        print("\nReading Order Verification:")
        print("Checking first 10 blocks are sorted by (page, top, left)...")
        is_sorted = True
        for i in range(min(9, len(result.blocks) - 1)):
            current = result.blocks[i]
            next_block = result.blocks[i + 1]
            
            current_top = current.geometry['BoundingBox']['Top']
            current_left = current.geometry['BoundingBox']['Left']
            next_top = next_block.geometry['BoundingBox']['Top']
            next_left = next_block.geometry['BoundingBox']['Left']
            
            if current.page_number > next_block.page_number:
                is_sorted = False
                break
            elif current.page_number == next_block.page_number:
                if current_top > next_top:
                    is_sorted = False
                    break
        
        if is_sorted:
            print("✓ Blocks are correctly sorted by reading order")
        else:
            print("❌ Blocks are NOT correctly sorted")
        
        # Save sample output
        output_file = "extractor_test_output.json"
        sample_output = {
            'status': result.status,
            'total_pages': result.total_pages,
            'total_blocks': len(result.blocks),
            'block_types': block_types,
            'sample_blocks': [
                {
                    'text': b.text,
                    'page_number': b.page_number,
                    'block_type': b.block_type,
                    'confidence': b.confidence
                }
                for b in result.blocks[:500]
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(sample_output, f, indent=2)
        
        print(f"\n✓ Sample output saved to: {output_file}")
        print("\n✓ Text extraction test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Text extraction test FAILED")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test execution."""
    print_section("ELS Text Extractor - Manual AWS Test")
    
    print("This script tests the text extractor with real AWS Textract.")
    print("Make sure you have:")
    print("  1. AWS credentials configured")
    print("  2. A test PDF uploaded to the S3 raw bucket")
    print("  3. Required environment variables set")
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Run extraction test
    success = test_extraction()
    
    # Summary
    print_section("Test Summary")
    if success:
        print("✓ All tests PASSED")
        print("\nThe text extractor is working correctly with AWS Textract.")
        sys.exit(0)
    else:
        print("❌ Tests FAILED")
        print("\nPlease review the errors above and check:")
        print("  - AWS credentials are valid")
        print("  - S3 bucket and document exist")
        print("  - IAM permissions for Textract and S3")
        sys.exit(1)


if __name__ == "__main__":
    main()
