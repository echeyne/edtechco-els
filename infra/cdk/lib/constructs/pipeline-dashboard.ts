import * as cdk from "aws-cdk-lib";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";

export interface PipelineDashboardProps {
  environmentName: string;
  /**
   * Step Functions state machine name for execution metrics.
   * e.g. "els-pipeline-dev"
   */
  stateMachineName: string;
}

/**
 * CloudWatch dashboard for monitoring ELS pipeline cost, latency,
 * and token usage across Bedrock LLM calls.
 *
 * Reads from:
 * - Custom metrics emitted by els_pipeline.metrics under the ELS/Pipeline namespace
 * - Lambda function metrics (duration, errors, invocations)
 * - Step Functions execution metrics
 * - CloudWatch Logs Insights queries against structured LLM_METRICS logs
 */
export class PipelineDashboard extends Construct {
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: PipelineDashboardProps) {
    super(scope, id);

    const env = props.environmentName;
    const namespace = "ELS/Pipeline";

    this.dashboard = new cloudwatch.Dashboard(this, "Dashboard", {
      dashboardName: `els-pipeline-metrics-${env}`,
      defaultInterval: cdk.Duration.hours(24),
    });

    // ====================================================================
    // Row 1: Cost overview
    // ====================================================================

    const totalCostDetection = new cloudwatch.Metric({
      namespace,
      metricName: "EstimatedCostUSD",
      dimensionsMap: { Stage: "detection" },
      statistic: "Sum",
      period: cdk.Duration.hours(1),
      label: "Detection Cost",
    });

    const totalCostParsing = new cloudwatch.Metric({
      namespace,
      metricName: "EstimatedCostUSD",
      dimensionsMap: { Stage: "parsing" },
      statistic: "Sum",
      period: cdk.Duration.hours(1),
      label: "Parsing Cost",
    });

    this.dashboard.addWidgets(
      new cloudwatch.SingleValueWidget({
        title: "Total Estimated Cost (24h)",
        metrics: [
          new cloudwatch.Metric({
            namespace,
            metricName: "EstimatedCostUSD",
            statistic: "Sum",
            period: cdk.Duration.hours(24),
            label: "Total Cost USD",
          }),
        ],
        width: 6,
        height: 4,
      }),
      new cloudwatch.GraphWidget({
        title: "Cost by Stage (hourly)",
        left: [totalCostDetection, totalCostParsing],
        width: 10,
        height: 4,
        stacked: true,
      }),
      new cloudwatch.SingleValueWidget({
        title: "LLM Calls (24h)",
        metrics: [
          new cloudwatch.Metric({
            namespace,
            metricName: "LLMCallCount",
            statistic: "Sum",
            period: cdk.Duration.hours(24),
            label: "Total Calls",
          }),
        ],
        width: 4,
        height: 4,
      }),
      new cloudwatch.SingleValueWidget({
        title: "LLM Errors (24h)",
        metrics: [
          new cloudwatch.Metric({
            namespace,
            metricName: "LLMCallErrors",
            statistic: "Sum",
            period: cdk.Duration.hours(24),
            label: "Errors",
          }),
        ],
        width: 4,
        height: 4,
      }),
    );

    // ====================================================================
    // Row 2: Token usage
    // ====================================================================

    const inputTokensDetection = new cloudwatch.Metric({
      namespace,
      metricName: "InputTokens",
      dimensionsMap: { Stage: "detection" },
      statistic: "Sum",
      period: cdk.Duration.hours(1),
      label: "Detection Input",
    });

    const outputTokensDetection = new cloudwatch.Metric({
      namespace,
      metricName: "OutputTokens",
      dimensionsMap: { Stage: "detection" },
      statistic: "Sum",
      period: cdk.Duration.hours(1),
      label: "Detection Output",
    });

    const inputTokensParsing = new cloudwatch.Metric({
      namespace,
      metricName: "InputTokens",
      dimensionsMap: { Stage: "parsing" },
      statistic: "Sum",
      period: cdk.Duration.hours(1),
      label: "Parsing Input",
    });

    const outputTokensParsing = new cloudwatch.Metric({
      namespace,
      metricName: "OutputTokens",
      dimensionsMap: { Stage: "parsing" },
      statistic: "Sum",
      period: cdk.Duration.hours(1),
      label: "Parsing Output",
    });

    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "Token Usage — Detection (hourly)",
        left: [inputTokensDetection, outputTokensDetection],
        width: 12,
        height: 6,
        stacked: true,
      }),
      new cloudwatch.GraphWidget({
        title: "Token Usage — Parsing (hourly)",
        left: [inputTokensParsing, outputTokensParsing],
        width: 12,
        height: 6,
        stacked: true,
      }),
    );

    // ====================================================================
    // Row 3: LLM latency
    // ====================================================================

    const latencyDetection = new cloudwatch.Metric({
      namespace,
      metricName: "LLMLatency",
      dimensionsMap: { Stage: "detection" },
      period: cdk.Duration.minutes(5),
    });

    const latencyParsing = new cloudwatch.Metric({
      namespace,
      metricName: "LLMLatency",
      dimensionsMap: { Stage: "parsing" },
      period: cdk.Duration.minutes(5),
    });

    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "LLM Latency — Detection",
        left: [
          latencyDetection.with({ statistic: "p50", label: "p50" }),
          latencyDetection.with({ statistic: "p90", label: "p90" }),
          latencyDetection.with({ statistic: "p99", label: "p99" }),
          latencyDetection.with({ statistic: "Maximum", label: "Max" }),
        ],
        width: 12,
        height: 6,
        leftYAxis: { label: "ms" },
      }),
      new cloudwatch.GraphWidget({
        title: "LLM Latency — Parsing",
        left: [
          latencyParsing.with({ statistic: "p50", label: "p50" }),
          latencyParsing.with({ statistic: "p90", label: "p90" }),
          latencyParsing.with({ statistic: "p99", label: "p99" }),
          latencyParsing.with({ statistic: "Maximum", label: "Max" }),
        ],
        width: 12,
        height: 6,
        leftYAxis: { label: "ms" },
      }),
    );

    // ====================================================================
    // Row 4: Retries
    // ====================================================================

    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "Retries by Stage",
        left: [
          new cloudwatch.Metric({
            namespace,
            metricName: "RetryCount",
            dimensionsMap: { Stage: "detection" },
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Detection Retries",
          }),
          new cloudwatch.Metric({
            namespace,
            metricName: "RetryCount",
            dimensionsMap: { Stage: "parsing" },
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Parsing Retries",
          }),
        ],
        width: 12,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: "LLM Errors by Stage",
        left: [
          new cloudwatch.Metric({
            namespace,
            metricName: "LLMCallErrors",
            dimensionsMap: { Stage: "detection" },
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Detection Errors",
          }),
          new cloudwatch.Metric({
            namespace,
            metricName: "LLMCallErrors",
            dimensionsMap: { Stage: "parsing" },
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Parsing Errors",
          }),
        ],
        width: 12,
        height: 6,
      }),
    );

    // ====================================================================
    // Row 5: Lambda function metrics (duration, errors, invocations)
    // ====================================================================

    const llmLambdas = [
      { name: `els-detect-batch-${env}`, label: "Detect Batch" },
      { name: `els-parse-batch-${env}`, label: "Parse Batch" },
      { name: `els-structure-detector-${env}`, label: "Detector" },
      { name: `els-hierarchy-parser-${env}`, label: "Parser" },
    ];

    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "Lambda Duration (LLM stages)",
        left: llmLambdas.map(
          (fn) =>
            new cloudwatch.Metric({
              namespace: "AWS/Lambda",
              metricName: "Duration",
              dimensionsMap: { FunctionName: fn.name },
              statistic: "Average",
              period: cdk.Duration.minutes(5),
              label: fn.label,
            }),
        ),
        width: 12,
        height: 6,
        leftYAxis: { label: "ms" },
      }),
      new cloudwatch.GraphWidget({
        title: "Lambda Errors (LLM stages)",
        left: llmLambdas.map(
          (fn) =>
            new cloudwatch.Metric({
              namespace: "AWS/Lambda",
              metricName: "Errors",
              dimensionsMap: { FunctionName: fn.name },
              statistic: "Sum",
              period: cdk.Duration.minutes(5),
              label: fn.label,
            }),
        ),
        width: 12,
        height: 6,
      }),
    );

    // ====================================================================
    // Row 6: Step Functions execution metrics
    // ====================================================================

    const sfnDimensions = {
      StateMachineArn: `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:${props.stateMachineName}`,
    };

    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "Pipeline Executions",
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/States",
            metricName: "ExecutionsStarted",
            dimensionsMap: sfnDimensions,
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Started",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/States",
            metricName: "ExecutionsSucceeded",
            dimensionsMap: sfnDimensions,
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Succeeded",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/States",
            metricName: "ExecutionsFailed",
            dimensionsMap: sfnDimensions,
            statistic: "Sum",
            period: cdk.Duration.hours(1),
            label: "Failed",
          }),
        ],
        width: 12,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: "Pipeline Execution Duration",
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/States",
            metricName: "ExecutionTime",
            dimensionsMap: sfnDimensions,
            statistic: "Average",
            period: cdk.Duration.hours(1),
            label: "Avg Duration",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/States",
            metricName: "ExecutionTime",
            dimensionsMap: sfnDimensions,
            statistic: "Maximum",
            period: cdk.Duration.hours(1),
            label: "Max Duration",
          }),
        ],
        width: 12,
        height: 6,
        leftYAxis: { label: "ms" },
      }),
    );

    // ====================================================================
    // Row 7: Logs Insights query widget for per-run cost breakdown
    // ====================================================================

    // The detect-batch and parse-batch Lambdas emit the LLM_METRICS logs
    const detectBatchLogGroup = `/aws/lambda/els-detect-batch-${env}`;
    const parseBatchLogGroup = `/aws/lambda/els-parse-batch-${env}`;
    const detectorLogGroup = `/aws/lambda/els-structure-detector-${env}`;
    const parserLogGroup = `/aws/lambda/els-hierarchy-parser-${env}`;

    this.dashboard.addWidgets(
      new cloudwatch.LogQueryWidget({
        title: "Cost per Pipeline Run (last 7 days)",
        logGroupNames: [
          detectBatchLogGroup,
          parseBatchLogGroup,
          detectorLogGroup,
          parserLogGroup,
        ],
        queryLines: [
          "filter @message like /LLM_METRICS/",
          'parse @message "LLM_METRICS: *" as metrics_json',
          "| stats sum(estimated_cost_usd) as total_cost, sum(input_tokens) as total_input, sum(output_tokens) as total_output, count(*) as llm_calls by run_id",
          "| sort total_cost desc",
          "| limit 20",
        ],
        width: 24,
        height: 8,
        view: cloudwatch.LogQueryVisualizationType.TABLE,
      }),
    );

    // ====================================================================
    // Row 8: Per-state cost breakdown
    // ====================================================================

    this.dashboard.addWidgets(
      new cloudwatch.LogQueryWidget({
        title: "Cost per State (last 7 days)",
        logGroupNames: [
          detectBatchLogGroup,
          parseBatchLogGroup,
          detectorLogGroup,
          parserLogGroup,
        ],
        queryLines: [
          "filter @message like /LLM_METRICS/",
          'parse @message "LLM_METRICS: *" as metrics_json',
          "| stats sum(estimated_cost_usd) as total_cost, sum(input_tokens) as total_input, sum(output_tokens) as total_output, count(*) as llm_calls by state",
          "| sort total_cost desc",
        ],
        width: 12,
        height: 6,
        view: cloudwatch.LogQueryVisualizationType.TABLE,
      }),
      new cloudwatch.LogQueryWidget({
        title: "Avg Latency per Stage (last 7 days)",
        logGroupNames: [
          detectBatchLogGroup,
          parseBatchLogGroup,
          detectorLogGroup,
          parserLogGroup,
        ],
        queryLines: [
          "filter @message like /LLM_METRICS/",
          'parse @message "LLM_METRICS: *" as metrics_json',
          "| stats avg(latency_ms) as avg_latency, max(latency_ms) as max_latency, count(*) as calls by stage",
          "| sort stage",
        ],
        width: 12,
        height: 6,
        view: cloudwatch.LogQueryVisualizationType.TABLE,
      }),
    );
  }
}
