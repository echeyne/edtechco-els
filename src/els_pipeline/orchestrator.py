"""
Pipeline orchestrator for the ELS normalization pipeline.

This module provides functions to start, monitor, and re-run pipeline stages.
The pipeline executes stages in order: ingestion → extraction → detection → 
parsing → validation → embedding → recommendation → persistence.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError

from .models import PipelineStageResult, PipelineRunResult
from .config import Config

logger = logging.getLogger(__name__)

# Lazy-initialized AWS clients (initialized on first use to avoid import-time boto3 calls)
_stepfunctions_client = None
_s3_client = None


def _get_stepfunctions_client():
    """Get or create Step Functions client."""
    global _stepfunctions_client
    if _stepfunctions_client is None:
        _stepfunctions_client = boto3.client('stepfunctions', region_name=Config.AWS_REGION)
    return _stepfunctions_client


def _get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    return _s3_client


def start_pipeline(
    s3_key: str,
    country: str,
    state: str,
    version_year: int,
    state_machine_arn: Optional[str] = None
) -> str:
    """
    Start a new pipeline execution.
    
    Args:
        s3_key: S3 key of the raw document to process
        country: Two-letter ISO 3166-1 alpha-2 country code
        state: State/province/region code
        version_year: Version year of the standards document
        state_machine_arn: ARN of the Step Functions state machine (optional, uses config if not provided)
    
    Returns:
        run_id: Unique identifier for this pipeline run
    
    Raises:
        ValueError: If country code is invalid or required parameters are missing
        ClientError: If Step Functions execution fails to start
    """
    # Validate country code format
    if not country or len(country) != 2 or not country.isupper():
        raise ValueError(f"Invalid country code: {country}. Must be a 2-letter uppercase ISO 3166-1 alpha-2 code.")
    
    # Validate required parameters
    if not s3_key:
        raise ValueError("s3_key is required")
    if not state:
        raise ValueError("state is required")
    if not version_year or version_year < 2000 or version_year > 2100:
        raise ValueError(f"Invalid version_year: {version_year}")
    
    # Generate unique run ID
    run_id = f"pipeline-{country}-{state}-{version_year}-{uuid.uuid4().hex[:8]}"
    
    # Extract filename from S3 key
    filename = s3_key.split('/')[-1] if '/' in s3_key else s3_key
    
    # Prepare execution input
    execution_input = {
        "run_id": run_id,
        "file_path": s3_key,
        "country": country,
        "state": state,
        "version_year": version_year,
        "s3_key": s3_key,
        "source_url": "",  # Optional: can be provided by caller in future
        "publishing_agency": "",  # Optional: can be provided by caller in future
        "filename": filename,
        "started_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Get state machine ARN from config if not provided
    if not state_machine_arn:
        state_machine_arn = Config.STEP_FUNCTIONS_STATE_MACHINE_ARN
    
    try:
        # Start Step Functions execution
        response = _get_stepfunctions_client().start_execution(
            stateMachineArn=state_machine_arn,
            name=run_id,
            input=json.dumps(execution_input)
        )
        
        logger.info(
            f"Started pipeline execution: run_id={run_id}, "
            f"country={country}, state={state}, year={version_year}, "
            f"execution_arn={response['executionArn']}"
        )
        
        return run_id
        
    except ClientError as e:
        logger.error(f"Failed to start pipeline execution: {e}")
        raise


def rerun_stage(
    run_id: str,
    stage_name: str,
    state_machine_arn: Optional[str] = None
) -> PipelineStageResult:
    """
    Re-run a specific pipeline stage for a given run.
    
    This function reads the output from the previous stage and re-executes
    the specified stage independently.
    
    Args:
        run_id: Unique identifier of the pipeline run
        stage_name: Name of the stage to re-run (e.g., "validation", "embedding")
        state_machine_arn: ARN of the Step Functions state machine (optional)
    
    Returns:
        PipelineStageResult: Result of the re-run stage
    
    Raises:
        ValueError: If run_id or stage_name is invalid
        ClientError: If stage re-execution fails
    """
    # Validate inputs
    if not run_id:
        raise ValueError("run_id is required")
    if not stage_name:
        raise ValueError("stage_name is required")
    
    valid_stages = {
        "ingestion", "text_extraction", "structure_detection",
        "hierarchy_parsing", "validation", "embedding_generation",
        "recommendation_generation", "data_persistence"
    }
    
    if stage_name not in valid_stages:
        raise ValueError(
            f"Invalid stage_name: {stage_name}. "
            f"Must be one of: {', '.join(sorted(valid_stages))}"
        )
    
    try:
        # Get the current pipeline status to find the previous stage output
        pipeline_status = get_pipeline_status(run_id)
        
        # Find the stage to re-run and its input
        stage_index = None
        for i, stage in enumerate(pipeline_status.stages):
            if stage.stage_name == stage_name:
                stage_index = i
                break
        
        if stage_index is None:
            raise ValueError(f"Stage {stage_name} not found in pipeline run {run_id}")
        
        # Get input from previous stage (or initial input for first stage)
        if stage_index == 0:
            # First stage uses the original document
            stage_input = {
                "run_id": run_id,
                "document_s3_key": pipeline_status.document_s3_key,
                "country": pipeline_status.country,
                "state": pipeline_status.state,
                "version_year": pipeline_status.version_year
            }
        else:
            # Use output from previous stage
            previous_stage = pipeline_status.stages[stage_index - 1]
            stage_input = {
                "run_id": run_id,
                "input_artifact": previous_stage.output_artifact,
                "country": pipeline_status.country,
                "state": pipeline_status.state,
                "version_year": pipeline_status.version_year
            }
        
        # Create a new execution for just this stage
        rerun_id = f"{run_id}-rerun-{stage_name}-{uuid.uuid4().hex[:8]}"
        
        # Get state machine ARN from config if not provided
        if not state_machine_arn:
            state_machine_arn = Config.STEP_FUNCTIONS_STATE_MACHINE_ARN
        
        start_time = time.time()
        
        # Start the stage execution
        # Note: In a real implementation, this would invoke a specific Lambda
        # or use a Step Functions feature to run a single state
        response = _get_stepfunctions_client().start_execution(
            stateMachineArn=state_machine_arn,
            name=rerun_id,
            input=json.dumps({
                **stage_input,
                "stage_to_run": stage_name,
                "is_rerun": True
            })
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"Re-ran stage {stage_name} for run {run_id}: "
            f"rerun_id={rerun_id}, execution_arn={response['executionArn']}"
        )
        
        # Return a stage result
        # In a real implementation, we would wait for the execution to complete
        # or return immediately and let the caller poll for status
        return PipelineStageResult(
            stage_name=stage_name,
            status="running",
            duration_ms=duration_ms,
            output_artifact=f"s3://rerun-output/{rerun_id}/{stage_name}",
            error=None
        )
        
    except ClientError as e:
        logger.error(f"Failed to re-run stage {stage_name} for run {run_id}: {e}")
        raise


def get_pipeline_status(run_id: str) -> PipelineRunResult:
    """
    Get the current status of a pipeline run.
    
    This function queries the Step Functions execution history and constructs
    a PipelineRunResult with all stage results and totals.
    
    Args:
        run_id: Unique identifier of the pipeline run
    
    Returns:
        PipelineRunResult: Current status of the pipeline run
    
    Raises:
        ValueError: If run_id is invalid
        ClientError: If execution status cannot be retrieved
    """
    if not run_id:
        raise ValueError("run_id is required")
    
    try:
        # Parse country, state, and year from run_id
        # Format: pipeline-{country}-{state}-{year}-{uuid}
        parts = run_id.split('-')
        if len(parts) < 5 or parts[0] != 'pipeline':
            raise ValueError(f"Invalid run_id format: {run_id}")
        
        country = parts[1]
        state = parts[2]
        version_year = int(parts[3])
        
        # In a real implementation, we would:
        # 1. Query Step Functions for execution status
        # 2. Parse the execution history to extract stage results
        # 3. Query the database for totals (indicators, validated, embedded, recommendations)
        
        # For now, return a placeholder result
        # This would be replaced with actual Step Functions API calls
        logger.info(f"Getting pipeline status for run_id={run_id}")
        
        # Placeholder: In production, query Step Functions and database
        return PipelineRunResult(
            run_id=run_id,
            document_s3_key=f"{country}/{state}/{version_year}/placeholder.pdf",
            country=country,
            state=state,
            version_year=version_year,
            stages=[],
            total_indicators=0,
            total_validated=0,
            total_embedded=0,
            total_recommendations=0,
            status="running"
        )
        
    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse run_id {run_id}: {e}")
        raise ValueError(f"Invalid run_id format: {run_id}")
    except ClientError as e:
        logger.error(f"Failed to get pipeline status for run {run_id}: {e}")
        raise


def _get_execution_arn(run_id: str, state_machine_arn: str) -> Optional[str]:
    """
    Helper function to get the execution ARN for a given run_id.
    
    Args:
        run_id: Unique identifier of the pipeline run
        state_machine_arn: ARN of the Step Functions state machine
    
    Returns:
        Execution ARN if found, None otherwise
    """
    try:
        # List executions for the state machine
        response = _get_stepfunctions_client().list_executions(
            stateMachineArn=state_machine_arn,
            maxResults=100
        )
        
        # Find the execution with matching name (run_id)
        for execution in response.get('executions', []):
            if execution['name'] == run_id:
                return execution['executionArn']
        
        return None
        
    except ClientError as e:
        logger.error(f"Failed to list executions: {e}")
        return None


def _parse_execution_history(execution_arn: str) -> Dict[str, Any]:
    """
    Helper function to parse Step Functions execution history.
    
    Args:
        execution_arn: ARN of the Step Functions execution
    
    Returns:
        Dictionary containing parsed stage results and totals
    """
    try:
        # Get execution history
        response = _get_stepfunctions_client().get_execution_history(
            executionArn=execution_arn,
            maxResults=1000,
            reverseOrder=False
        )
        
        stages = []
        totals = {
            'total_indicators': 0,
            'total_validated': 0,
            'total_embedded': 0,
            'total_recommendations': 0
        }
        
        # Parse events to extract stage results
        # This is a simplified version - real implementation would be more complex
        for event in response.get('events', []):
            event_type = event.get('type')
            
            # Look for task state completed events
            if event_type == 'TaskStateExited':
                details = event.get('stateExitedEventDetails', {})
                stage_name = details.get('name', 'unknown')
                output = json.loads(details.get('output', '{}'))
                
                # Extract stage result
                stage_result = PipelineStageResult(
                    stage_name=stage_name,
                    status=output.get('status', 'success'),
                    duration_ms=output.get('duration_ms', 0),
                    output_artifact=output.get('output_artifact', ''),
                    error=output.get('error')
                )
                stages.append(stage_result)
                
                # Update totals if present in output
                if 'total_indicators' in output:
                    totals['total_indicators'] = output['total_indicators']
                if 'total_validated' in output:
                    totals['total_validated'] = output['total_validated']
                if 'total_embedded' in output:
                    totals['total_embedded'] = output['total_embedded']
                if 'total_recommendations' in output:
                    totals['total_recommendations'] = output['total_recommendations']
        
        return {
            'stages': stages,
            **totals
        }
        
    except ClientError as e:
        logger.error(f"Failed to get execution history: {e}")
        return {
            'stages': [],
            'total_indicators': 0,
            'total_validated': 0,
            'total_embedded': 0,
            'total_recommendations': 0
        }
