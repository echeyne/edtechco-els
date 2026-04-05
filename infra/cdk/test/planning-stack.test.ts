import * as cdk from "aws-cdk-lib";
import { Template, Match } from "aws-cdk-lib/assertions";
import { ElsPlanningStack } from "../lib/planning-stack";

describe("ElsPlanningStack", () => {
  describe("without custom domain", () => {
    let template: Template;

    beforeAll(() => {
      const app = new cdk.App();
      const stack = new ElsPlanningStack(app, "TestPlanningStack", {
        environmentName: "dev",
        pipelineStackName: "els-pipeline-dev",
        descopeProjectId: "test-descope-id",
        env: { region: "us-east-1", account: "123456789012" },
      });
      template = Template.fromStack(stack);
    });

    // ── S3 Bucket ──

    test("S3 bucket has public access blocked", () => {
      template.hasResourceProperties("AWS::S3::Bucket", {
        PublicAccessBlockConfiguration: {
          BlockPublicAcls: true,
          BlockPublicPolicy: true,
          IgnorePublicAcls: true,
          RestrictPublicBuckets: true,
        },
      });
    });

    test("S3 bucket has S3-managed encryption", () => {
      template.hasResourceProperties("AWS::S3::Bucket", {
        BucketEncryption: {
          ServerSideEncryptionConfiguration: [
            {
              ServerSideEncryptionByDefault: {
                SSEAlgorithm: "AES256",
              },
            },
          ],
        },
      });
    });

    // ── CloudFront ──

    test("CloudFront distribution exists", () => {
      template.resourceCountIs("AWS::CloudFront::Distribution", 1);
    });

    // ── Lambda ──

    test("Lambda function uses nodejs22.x runtime with 120s timeout", () => {
      template.hasResourceProperties("AWS::Lambda::Function", {
        Runtime: "nodejs22.x",
        Timeout: 120,
      });
    });

    // ── API Gateway with CORS ──

    test("HTTP API Gateway exists with CORS", () => {
      template.hasResourceProperties("AWS::ApiGatewayV2::Api", {
        ProtocolType: "HTTP",
        CorsConfiguration: {
          AllowOrigins: Match.arrayWith(["http://localhost:5173"]),
          AllowMethods: Match.arrayWith([
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
          ]),
          AllowHeaders: Match.arrayWith(["Content-Type", "Authorization"]),
        },
      });
    });

    // ── Bedrock Guardrail ──

    test("Bedrock Guardrail exists with content filters", () => {
      template.hasResourceProperties("AWS::Bedrock::Guardrail", {
        ContentPolicyConfig: {
          FiltersConfig: Match.arrayWith([
            Match.objectLike({
              Type: "SEXUAL",
              InputStrength: "HIGH",
              OutputStrength: "HIGH",
            }),
            Match.objectLike({
              Type: "VIOLENCE",
              InputStrength: "HIGH",
              OutputStrength: "HIGH",
            }),
            Match.objectLike({
              Type: "HATE",
              InputStrength: "HIGH",
              OutputStrength: "HIGH",
            }),
            Match.objectLike({
              Type: "INSULTS",
              InputStrength: "HIGH",
              OutputStrength: "HIGH",
            }),
            Match.objectLike({
              Type: "MISCONDUCT",
              InputStrength: "HIGH",
              OutputStrength: "HIGH",
            }),
            Match.objectLike({
              Type: "PROMPT_ATTACK",
              InputStrength: "HIGH",
              OutputStrength: "NONE",
            }),
          ]),
        },
      });
    });

    test("Bedrock Guardrail has topic deny policies", () => {
      template.hasResourceProperties("AWS::Bedrock::Guardrail", {
        TopicPolicyConfig: {
          TopicsConfig: Match.arrayWith([
            Match.objectLike({ Name: "MedicalAdvice", Type: "DENY" }),
            Match.objectLike({ Name: "DevelopmentalDiagnoses", Type: "DENY" }),
            Match.objectLike({ Name: "Politics", Type: "DENY" }),
            Match.objectLike({ Name: "Religion", Type: "DENY" }),
            Match.objectLike({ Name: "PersonalRelationships", Type: "DENY" }),
            Match.objectLike({ Name: "FinancialAdvice", Type: "DENY" }),
          ]),
        },
      });
    });

    test("Bedrock Guardrail Version exists", () => {
      template.resourceCountIs("AWS::Bedrock::GuardrailVersion", 1);
    });

    // ── AgentCore Runtime ──

    test("AgentCore Runtime exists with direct code deploy", () => {
      template.hasResourceProperties(
        "AWS::BedrockAgentCore::Runtime",
        Match.objectLike({
          AgentRuntimeName: "els_planning_agent_dev",
        }),
      );
    });

    test("AgentCore Runtime has environment variables", () => {
      template.hasResourceProperties(
        "AWS::BedrockAgentCore::Runtime",
        Match.objectLike({
          EnvironmentVariables: Match.objectLike({
            DB_NAME: "els_pipeline",
          }),
        }),
      );
    });

    // ── Conditional: no custom domain ──

    test("no ACM Certificate resources", () => {
      template.resourceCountIs("AWS::CertificateManager::Certificate", 0);
    });

    test("no Route53 RecordSet resources", () => {
      template.resourceCountIs("AWS::Route53::RecordSet", 0);
    });

    // ── Outputs ──

    test("outputs PlanningFrontendBucketName", () => {
      template.hasOutput("PlanningFrontendBucketName", {});
    });

    test("outputs PlanningCloudFrontDomainName", () => {
      template.hasOutput("PlanningCloudFrontDomainName", {});
    });

    test("outputs PlanningCloudFrontDistributionId", () => {
      template.hasOutput("PlanningCloudFrontDistributionId", {});
    });

    test("outputs PlanningApiGatewayUrl", () => {
      template.hasOutput("PlanningApiGatewayUrl", {});
    });

    test("outputs PlanningApiLambdaFunctionName", () => {
      template.hasOutput("PlanningApiLambdaFunctionName", {});
    });

    test("outputs PlanningGuardrailId", () => {
      template.hasOutput("PlanningGuardrailId", {});
    });

    test("outputs PlanningGuardrailVersion", () => {
      template.hasOutput("PlanningGuardrailVersion", {});
    });

    test("outputs PlanningAgentCoreRoleArn", () => {
      template.hasOutput("PlanningAgentCoreRoleArn", {});
    });
  });

  describe("with custom domain", () => {
    let template: Template;

    beforeAll(() => {
      const app = new cdk.App();
      const stack = new ElsPlanningStack(app, "TestPlanningStackDomain", {
        environmentName: "dev",
        pipelineStackName: "els-pipeline-dev",
        descopeProjectId: "test-descope-id",
        customDomainName: "planning.example.com",
        hostedZoneId: "Z1234567890",
        env: { region: "us-east-1", account: "123456789012" },
      });
      template = Template.fromStack(stack);
    });

    test("ACM Certificate exists with Retain policy", () => {
      template.resourceCountIs("AWS::CertificateManager::Certificate", 1);
      template.hasResource("AWS::CertificateManager::Certificate", {
        DeletionPolicy: "Retain",
        UpdateReplacePolicy: "Retain",
      });
    });

    test("Route53 RecordSet exists with Retain policy", () => {
      template.resourceCountIs("AWS::Route53::RecordSet", 1);
      template.hasResource("AWS::Route53::RecordSet", {
        DeletionPolicy: "Retain",
        UpdateReplacePolicy: "Retain",
      });
    });

    test("outputs PlanningCustomDomainUrl", () => {
      template.hasOutput("PlanningCustomDomainUrl", {});
    });
  });
});
