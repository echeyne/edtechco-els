"""Pipeline metrics and cost tracking for LLM calls.

Emits structured CloudWatch metrics and logs for Bedrock API usage,
enabling cost analysis and latency monitoring across pipeline runs.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List

import boto3
from botocore.exceptions import ClientError

from .config import Config

logger = logging.getLogger(__name__)

# Bedrock pricing per 1K tokens (us-east-1, as of April 2026)
# Update these when prices change or models change
BEDROCK_PRICING = {
    "us.anthropic.claude-opus-4-7": {"input_per_1k": 0.005, "output_per_1k": 0.025},
    "anthropic.claude-opus-4-7": {"input_per_1k": 0.005, "output_per_1k": 0.025},
    "us.anthropic.claude-sonnet-4-6": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "anthropic.claude-sonnet-4-6": {"input_per_1k": 0.003, "output_per_1k": 0.015},
}


@dataclass
class LLMCallMetrics:
    """Metrics for a single Bedrock LLM invocation."""
    stage: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    retry_count: int = 0
    run_id: str = ""
    country: str = ""
    state: str = ""
    batch_index: Optional[int] = None
    chunk_index: Optional[int] = None
    success: bool = True
    error: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        pricing = BEDROCK_PRICING.get(self.model_id, {})
        input_cost = (self.input_tokens / 1000) * pricing.get("input_per_1k", 0)
        output_cost = (self.output_tokens / 1000) * pricing.get("output_per_1k", 0)
        return input_cost + output_cost


@dataclass
class PipelineRunMetrics:
    """Aggregated metrics for an entire pipeline run."""
    run_id: str
    country: str = ""
    state: str = ""
    version_year: int = 0
    document_pages: int = 0
    document_blocks: int = 0
    llm_calls: List[LLMCallMetrics] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.llm_calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.llm_calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(c.estimated_cost_usd for c in self.llm_calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.llm_calls)

    @property
    def detection_calls(self) -> List[LLMCallMetrics]:
        return [c for c in self.llm_calls if c.stage == "detection"]

    @property
    def parsing_calls(self) -> List[LLMCallMetrics]:
        return [c for c in self.llm_calls if c.stage == "parsing"]

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "country": self.country,
            "state": self.state,
            "version_year": self.version_year,
            "document_pages": self.document_pages,
            "document_blocks": self.document_blocks,
            "total_llm_calls": len(self.llm_calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_latency_ms": round(self.total_latency_ms, 1),
            "detection": {
                "calls": len(self.detection_calls),
                "input_tokens": sum(c.input_tokens for c in self.detection_calls),
                "output_tokens": sum(c.output_tokens for c in self.detection_calls),
                "cost_usd": round(sum(c.estimated_cost_usd for c in self.detection_calls), 4),
                "latency_ms": round(sum(c.latency_ms for c in self.detection_calls), 1),
            },
            "parsing": {
                "calls": len(self.parsing_calls),
                "input_tokens": sum(c.input_tokens for c in self.parsing_calls),
                "output_tokens": sum(c.output_tokens for c in self.parsing_calls),
                "cost_usd": round(sum(c.estimated_cost_usd for c in self.parsing_calls), 4),
                "latency_ms": round(sum(c.latency_ms for c in self.parsing_calls), 1),
            },
        }


def extract_usage_from_response(response_body: Dict[str, Any]) -> Dict[str, int]:
    """
    Extract token usage from a Bedrock Claude response body.

    Claude responses include a 'usage' field:
    {
        "usage": {
            "input_tokens": 1234,
            "output_tokens": 567
        }
    }

    Args:
        response_body: Parsed JSON response from Bedrock

    Returns:
        Dict with input_tokens and output_tokens (defaults to 0 if missing)
    """
    usage = response_body.get("usage", {})
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


class MetricsTimer:
    """Context manager for timing LLM calls."""

    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0

    def __enter__(self):
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *args):
        self.end_time = time.monotonic()

    @property
    def elapsed_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


def emit_cloudwatch_metrics(call_metrics: LLMCallMetrics) -> None:
    """
    Emit CloudWatch custom metrics for a single LLM call.

    Publishes to the 'ELS/Pipeline' namespace with two dimension sets:
    1. Stage-only — used by dashboard aggregate widgets
    2. Stage + ModelId (+ optional State) — for drill-down analysis

    Args:
        call_metrics: Metrics from a single LLM invocation
    """
    try:
        cw = boto3.client("cloudwatch", region_name=Config.AWS_REGION)

        # Detailed dimensions for drill-down (Stage + ModelId + optional State)
        detailed_dims = [
            {"Name": "Stage", "Value": call_metrics.stage},
            {"Name": "ModelId", "Value": call_metrics.model_id},
        ]
        if call_metrics.state:
            detailed_dims.append({"Name": "State", "Value": call_metrics.state})

        # Aggregate dimension for dashboard widgets (Stage only)
        stage_dims = [{"Name": "Stage", "Value": call_metrics.stage}]

        base_metrics = [
            ("InputTokens", float(call_metrics.input_tokens), "Count"),
            ("OutputTokens", float(call_metrics.output_tokens), "Count"),
            ("LLMLatency", call_metrics.latency_ms, "Milliseconds"),
            ("EstimatedCostUSD", call_metrics.estimated_cost_usd, "None"),
            ("LLMCallCount", 1.0, "Count"),
        ]

        if call_metrics.retry_count > 0:
            base_metrics.append(("RetryCount", float(call_metrics.retry_count), "Count"))

        if not call_metrics.success:
            base_metrics.append(("LLMCallErrors", 1.0, "Count"))

        # Emit with both dimension sets so dashboard aggregates and
        # drill-down queries both find data.
        metric_data = []
        for name, value, unit in base_metrics:
            metric_data.append(
                {"MetricName": name, "Dimensions": stage_dims, "Value": value, "Unit": unit}
            )
            metric_data.append(
                {"MetricName": name, "Dimensions": detailed_dims, "Value": value, "Unit": unit}
            )

        cw.put_metric_data(Namespace="ELS/Pipeline", MetricData=metric_data)

    except ClientError as e:
        # Don't let metrics failures break the pipeline
        logger.warning(f"Failed to emit CloudWatch metrics: {e}")


def log_llm_call_metrics(call_metrics: LLMCallMetrics) -> None:
    """
    Log LLM call metrics as structured JSON for CloudWatch Logs Insights queries.

    Args:
        call_metrics: Metrics from a single LLM invocation
    """
    log_entry = {
        "metric_type": "llm_call",
        "stage": call_metrics.stage,
        "model_id": call_metrics.model_id,
        "input_tokens": call_metrics.input_tokens,
        "output_tokens": call_metrics.output_tokens,
        "total_tokens": call_metrics.total_tokens,
        "latency_ms": round(call_metrics.latency_ms, 1),
        "estimated_cost_usd": round(call_metrics.estimated_cost_usd, 6),
        "retry_count": call_metrics.retry_count,
        "run_id": call_metrics.run_id,
        "country": call_metrics.country,
        "state": call_metrics.state,
        "batch_index": call_metrics.batch_index,
        "chunk_index": call_metrics.chunk_index,
        "success": call_metrics.success,
    }
    if call_metrics.error:
        log_entry["error"] = call_metrics.error

    logger.info(f"LLM_METRICS: {json.dumps(log_entry)}")


def log_pipeline_run_summary(run_metrics: PipelineRunMetrics) -> None:
    """
    Log pipeline run summary as structured JSON.

    Args:
        run_metrics: Aggregated metrics for the pipeline run
    """
    logger.info(f"PIPELINE_METRICS: {json.dumps(run_metrics.summary())}")
