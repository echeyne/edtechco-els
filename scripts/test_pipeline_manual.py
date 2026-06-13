#!/usr/bin/env python3
"""
Manual AWS test script for the ELS core pipeline.

This script tests the complete pipeline execution with Step Functions,
monitors execution status and stage transitions, and verifies SNS
notifications.

Prerequisites:
1. AWS credentials configured (via ~/.aws/credentials or environment variables)
2. CloudFormation stack deployed with all core pipeline resources
3. Step Functions state machine created
4. All Lambda functions deployed
5. SNS topic created for notifications

Environment Variables:
- AWS_REGION: AWS region (default: us-east-1)
- ENVIRONMENT: Environment name (default: dev)
- STATE_MACHINE_ARN: ARN of the Step Functions state machine
- TEST_DOCUMENT_PATH: Path to test PDF document
- COUNTRY: Country code (default: US)
- STATE: State code (default: CA)
- VERSION_YEAR: Version year (default: 2021)

Usage:
    python scripts/test_pipeline_manual.py
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

import boto3
from botocore.exceptions import ClientError

# Load environment variables from .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from els_pipeline.orchestrator import start_pipeline, get_pipeline_status
from els_pipeline.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_prerequisites():
    """Check that all required AWS resources exist."""
    logger.info("Checking prerequisites...")
    
    # Check AWS credentials
    try:
        sts = boto3.client('sts', region_name=Config.AWS_REGION)
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account: {identity['Account']}")
        logger.info(f"AWS User/Role: {identity['Arn']}")
    except Exception as e:
        logger.error(f"Failed to get AWS credentials: {e}")
        return False
    
    # Check Step Functions state machine
    state_machine_arn = os.getenv('STATE_MACHINE_ARN', Config.STEP_FUNCTIONS_STATE_MACHINE_ARN)
    try:
        sfn = boto3.client('stepfunctions', region_name=Config.AWS_REGION)
        response = sfn.describe_state_machine(stateMachineArn=state_machine_arn)
        logger.info(f"State Machine: {response['name']}")
        logger.info(f"Status: {response['status']}")
    except ClientError as e:
        logger.error(f"Failed to describe state machine: {e}")
        logger.error(f"Make sure STATE_MACHINE_ARN is set correctly: {state_machine_arn}")
        return False
    
    # Check S3 buckets
    s3 = boto3.client('s3', region_name=Config.AWS_REGION)
    for bucket_name in [Config.S3_RAW_BUCKET, Config.S3_PROCESSED_BUCKET]:
        try:
            s3.head_bucket(Bucket=bucket_name)
            logger.info(f"S3 Bucket exists: {bucket_name}")
        except ClientError as e:
            logger.error(f"S3 Bucket not found: {bucket_name}")
            return False
    
    logger.info("All prerequisites met!")
    return True


def upload_test_document():
    """Upload a test document to S3 for processing."""
    test_doc_path = os.getenv('TEST_DOCUMENT_PATH')
    if not test_doc_path:
        logger.warning("TEST_DOCUMENT_PATH not set, skipping document upload")
        logger.info("You can manually upload a document to S3 and provide its key")
        return None
    
    if not os.path.exists(test_doc_path):
        logger.error(f"Test document not found: {test_doc_path}")
        return None
    
    country = os.getenv('COUNTRY', 'US')
    state = os.getenv('STATE', 'CA')
    version_year = int(os.getenv('VERSION_YEAR', '2021'))
    filename = os.path.basename(test_doc_path)
    
    s3_key = f"{country}/{state}/{version_year}/{filename}"
    
    logger.info(f"Uploading test document to S3: {s3_key}")
    
    try:
        s3 = boto3.client('s3', region_name=Config.AWS_REGION)
        with open(test_doc_path, 'rb') as f:
            s3.put_object(
                Bucket=Config.S3_RAW_BUCKET,
                Key=s3_key,
                Body=f,
                Metadata={
                    'country': country,
                    'state': state,
                    'version_year': str(version_year),
                    'upload_timestamp': datetime.utcnow().isoformat()
                }
            )
        logger.info(f"Document uploaded successfully: s3://{Config.S3_RAW_BUCKET}/{s3_key}")
        return s3_key
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        return None


def start_test_pipeline(file_path=None):
    """Start a test pipeline execution."""
    country = os.getenv('COUNTRY', 'US')
    state = os.getenv('STATE', 'CA')
    version_year = int(os.getenv('VERSION_YEAR', '2021'))
    
    if not file_path:
        # Use S3 key for file already uploaded
        filename = "california_all_standards_2021.pdf"
        file_path = f"{country}/{state}/{version_year}/{filename}"
        logger.info(f"Using S3 key: {file_path}")
    
    logger.info(f"Starting pipeline for: country={country}, state={state}, year={version_year}")
    
    try:
        state_machine_arn = os.getenv('STATE_MACHINE_ARN', Config.STEP_FUNCTIONS_STATE_MACHINE_ARN)
        run_id = start_pipeline(
            s3_key=file_path,
            country=country,
            state=state,
            version_year=version_year,
            state_machine_arn=state_machine_arn
        )
        logger.info(f"Pipeline started successfully!")
        logger.info(f"Run ID: {run_id}")
        return run_id
    except Exception as e:
        logger.error(f"Failed to start pipeline: {e}")
        return None


def monitor_pipeline_execution(run_id, max_wait_seconds=600):
    """Monitor pipeline execution and display progress."""
    logger.info(f"Monitoring pipeline execution: {run_id}")
    logger.info(f"Max wait time: {max_wait_seconds} seconds")
    
    sfn = boto3.client('stepfunctions', region_name=Config.AWS_REGION)
    state_machine_arn = os.getenv('STATE_MACHINE_ARN', Config.STEP_FUNCTIONS_STATE_MACHINE_ARN)
    
    # Find the execution ARN
    try:
        executions = sfn.list_executions(
            stateMachineArn=state_machine_arn,
            maxResults=100
        )
        
        execution_arn = None
        for execution in executions['executions']:
            if execution['name'] == run_id:
                execution_arn = execution['executionArn']
                break
        
        if not execution_arn:
            logger.error(f"Execution not found: {run_id}")
            return False
        
        logger.info(f"Execution ARN: {execution_arn}")
        
    except ClientError as e:
        logger.error(f"Failed to find execution: {e}")
        return False
    
    # Monitor execution status
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait_seconds:
        try:
            response = sfn.describe_execution(executionArn=execution_arn)
            status = response['status']
            
            if status != last_status:
                logger.info(f"Execution status: {status}")
                last_status = status
            
            if status == 'SUCCEEDED':
                logger.info("Pipeline completed successfully!")
                
                # Get execution output
                output = json.loads(response.get('output', '{}'))
                logger.info(f"Pipeline output: {json.dumps(output, indent=2)}")
                
                return True
            
            elif status == 'FAILED':
                logger.error("Pipeline execution failed!")
                
                # Get error details
                if 'error' in response:
                    logger.error(f"Error: {response['error']}")
                if 'cause' in response:
                    logger.error(f"Cause: {response['cause']}")
                
                return False
            
            elif status == 'TIMED_OUT':
                logger.error("Pipeline execution timed out!")
                return False
            
            elif status == 'ABORTED':
                logger.error("Pipeline execution was aborted!")
                return False
            
            # Still running, wait and check again
            time.sleep(5)
            
        except ClientError as e:
            logger.error(f"Failed to describe execution: {e}")
            return False
    
    logger.warning(f"Monitoring timed out after {max_wait_seconds} seconds")
    logger.info(f"Execution may still be running. Check AWS Console for status.")
    return False


def display_execution_history(run_id):
    """Display detailed execution history with stage transitions."""
    logger.info(f"Fetching execution history for: {run_id}")
    
    sfn = boto3.client('stepfunctions', region_name=Config.AWS_REGION)
    state_machine_arn = os.getenv('STATE_MACHINE_ARN', Config.STEP_FUNCTIONS_STATE_MACHINE_ARN)
    
    # Find the execution ARN
    try:
        executions = sfn.list_executions(
            stateMachineArn=state_machine_arn,
            maxResults=100
        )
        
        execution_arn = None
        for execution in executions['executions']:
            if execution['name'] == run_id:
                execution_arn = execution['executionArn']
                break
        
        if not execution_arn:
            logger.error(f"Execution not found: {run_id}")
            return
        
        # Get execution history
        response = sfn.get_execution_history(
            executionArn=execution_arn,
            maxResults=1000,
            reverseOrder=False
        )
        
        logger.info("\n" + "="*80)
        logger.info("EXECUTION HISTORY")
        logger.info("="*80)
        
        for event in response['events']:
            event_type = event['type']
            timestamp = event['timestamp']
            
            # Display relevant events
            if event_type in ['ExecutionStarted', 'ExecutionSucceeded', 'ExecutionFailed',
                             'TaskStateEntered', 'TaskStateExited', 'TaskFailed']:
                logger.info(f"\n[{timestamp}] {event_type}")
                
                if event_type == 'TaskStateEntered':
                    details = event.get('stateEnteredEventDetails', {})
                    logger.info(f"  State: {details.get('name', 'unknown')}")
                
                elif event_type == 'TaskStateExited':
                    details = event.get('stateExitedEventDetails', {})
                    logger.info(f"  State: {details.get('name', 'unknown')}")
                    output = details.get('output', '{}')
                    try:
                        output_obj = json.loads(output)
                        logger.info(f"  Output: {json.dumps(output_obj, indent=4)}")
                    except:
                        logger.info(f"  Output: {output}")
                
                elif event_type == 'TaskFailed':
                    details = event.get('taskFailedEventDetails', {})
                    logger.info(f"  Error: {details.get('error', 'unknown')}")
                    logger.info(f"  Cause: {details.get('cause', 'unknown')}")
        
        logger.info("\n" + "="*80)
        
    except ClientError as e:
        logger.error(f"Failed to get execution history: {e}")


def verify_sns_notifications():
    """Verify SNS topic exists and is configured correctly."""
    logger.info("Verifying SNS notifications...")
    
    sns = boto3.client('sns', region_name=Config.AWS_REGION)
    
    try:
        # List topics
        response = sns.list_topics()
        
        # Find ELS pipeline topic
        topic_arn = None
        for topic in response['Topics']:
            if 'els-pipeline-notifications' in topic['TopicArn']:
                topic_arn = topic['TopicArn']
                break
        
        if not topic_arn:
            logger.warning("SNS topic not found. Notifications may not be configured.")
            return False
        
        logger.info(f"SNS Topic: {topic_arn}")
        
        # Get topic attributes
        attrs = sns.get_topic_attributes(TopicArn=topic_arn)
        logger.info(f"Topic Name: {attrs['Attributes'].get('DisplayName', 'N/A')}")
        
        # List subscriptions
        subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn)
        logger.info(f"Subscriptions: {len(subs['Subscriptions'])}")
        
        for sub in subs['Subscriptions']:
            logger.info(f"  - {sub['Protocol']}: {sub['Endpoint']} ({sub['SubscriptionArn']})")
        
        return True
        
    except ClientError as e:
        logger.error(f"Failed to verify SNS notifications: {e}")
        return False


def main():
    """Main test execution."""
    logger.info("="*80)
    logger.info("ELS CORE PIPELINE MANUAL TEST")
    logger.info("="*80)
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'dev')}")
    logger.info(f"AWS Region: {Config.AWS_REGION}")
    logger.info("")
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        logger.error("Prerequisites check failed. Exiting.")
        sys.exit(1)
    
    logger.info("")
    
    # Step 2: Verify SNS notifications
    verify_sns_notifications()
    
    logger.info("")
    
    # Step 3: Start pipeline with local file
    run_id = start_test_pipeline()
    if not run_id:
        logger.error("Failed to start pipeline. Exiting.")
        sys.exit(1)
    
    logger.info("")
    
    # Step 4: Monitor execution
    success = monitor_pipeline_execution(run_id, max_wait_seconds=600)
    
    logger.info("")
    
    # Step 5: Display execution history
    display_execution_history(run_id)
    
    logger.info("")
    logger.info("="*80)
    if success:
        logger.info("TEST COMPLETED SUCCESSFULLY!")
    else:
        logger.info("TEST COMPLETED WITH ERRORS")
    logger.info("="*80)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
