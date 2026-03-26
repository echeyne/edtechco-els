import * as path from "path";
import * as cdk from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as bedrock from "aws-cdk-lib/aws-bedrock";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";
import { Construct } from "constructs";
import { FrontendDistribution } from "./constructs/frontend-distribution";

export interface ElsPlanningStackProps extends cdk.StackProps {
  environmentName: string;
  pipelineStackName: string;
  descopeProjectId: string;
  bedrockAgentModelId?: string;
  customDomainName?: string;
  hostedZoneId?: string;
}

export class ElsPlanningStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ElsPlanningStackProps) {
    super(scope, id, props);

    const env = props.environmentName;
    const accountId = cdk.Aws.ACCOUNT_ID;
    const region = cdk.Aws.REGION;

    // ========================================================================
    // Cross-Stack Imports
    // ========================================================================

    const databaseClusterArn = cdk.Fn.importValue(
      `${props.pipelineStackName}-DatabaseClusterArn`,
    );
    const databaseSecretArn = cdk.Fn.importValue(
      `${props.pipelineStackName}-DatabaseSecretArn`,
    );

    // ========================================================================
    // Planning API Lambda IAM Role (CfnRole L1 to match original CFN template)
    // ========================================================================

    const planningApiLambdaRole = new iam.CfnRole(
      this,
      "PlanningApiLambdaRole",
      {
        roleName: `els-planning-api-role-${env}`,
        assumeRolePolicyDocument: {
          Version: "2012-10-17",
          Statement: [
            {
              Effect: "Allow",
              Principal: { Service: "lambda.amazonaws.com" },
              Action: "sts:AssumeRole",
            },
          ],
        },
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "AgentCorePresignedUrl",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Sid: "AgentCorePresignedUrl",
                  Effect: "Allow",
                  Action: [
                    "bedrock-agentcore:InvokeRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream",
                  ],
                  Resource: `arn:aws:bedrock-agentcore:${region}:${accountId}:runtime/*`,
                },
              ],
            },
          },
          {
            policyName: "RdsDataReadOnly",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Sid: "RdsDataReadOnly",
                  Effect: "Allow",
                  Action: [
                    "rds-data:ExecuteStatement",
                    "rds-data:BatchExecuteStatement",
                  ],
                  Resource: databaseClusterArn,
                },
              ],
            },
          },
          {
            policyName: "SecretsManagerAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Sid: "SecretsManagerAccess",
                  Effect: "Allow",
                  Action: ["secretsmanager:GetSecretValue"],
                  Resource: databaseSecretArn,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Planning" },
        ],
      },
    );

    // ========================================================================
    // Planning API Lambda Function
    // ========================================================================

    const planningApiLambdaFunction = new lambda.CfnFunction(
      this,
      "PlanningApiLambdaFunction",
      {
        functionName: `els-planning-api-${env}`,
        runtime: "nodejs22.x",
        handler: "index.handler",
        role: planningApiLambdaRole.attrArn,
        timeout: 120,
        memorySize: 512,
        environment: {
          variables: {
            ENVIRONMENT: env,
            DB_CLUSTER_ARN: databaseClusterArn,
            DB_SECRET_ARN: databaseSecretArn,
            DB_NAME: "els_pipeline",
            DESCOPE_PROJECT_ID: props.descopeProjectId,
            AGENTCORE_RUNTIME_ARN: "", // Updated after AgentCore Runtime is created below
          },
        },
        code: {
          zipFile: `exports.handler = async () => ({ statusCode: 200, body: 'placeholder' });`,
        },
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Planning" },
        ],
      },
    );

    // ========================================================================
    // HTTP API Gateway (L1 constructs matching CloudFormation)
    // ========================================================================

    // Build CORS allow origins
    const corsAllowOrigins: string[] = [
      "http://localhost:5173",
      "http://localhost:4173",
    ];
    if (props.customDomainName) {
      corsAllowOrigins.push(`https://${props.customDomainName}`);
    }

    const apiGateway = new apigatewayv2.CfnApi(this, "PlanningApiGateway", {
      name: `els-planning-api-${env}`,
      protocolType: "HTTP",
      corsConfiguration: {
        allowOrigins: corsAllowOrigins,
        allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
        maxAge: 86400,
      },
    });

    const apiGatewayIntegration = new apigatewayv2.CfnIntegration(
      this,
      "PlanningApiGatewayIntegration",
      {
        apiId: apiGateway.ref,
        integrationType: "AWS_PROXY",
        integrationUri: planningApiLambdaFunction.attrArn,
        payloadFormatVersion: "2.0",
      },
    );

    new apigatewayv2.CfnRoute(this, "PlanningApiGatewayRoute", {
      apiId: apiGateway.ref,
      routeKey: "$default",
      target: `integrations/${apiGatewayIntegration.ref}`,
    });

    new apigatewayv2.CfnStage(this, "PlanningApiGatewayStage", {
      apiId: apiGateway.ref,
      stageName: "$default",
      autoDeploy: true,
    });

    // Lambda permission for API Gateway invocation
    new lambda.CfnPermission(this, "PlanningApiLambdaPermission", {
      functionName: planningApiLambdaFunction.ref,
      action: "lambda:InvokeFunction",
      principal: "apigateway.amazonaws.com",
      sourceArn: `arn:aws:execute-api:${region}:${accountId}:${apiGateway.ref}/*`,
    });

    // ========================================================================
    // Conditional Custom Domain: ACM Certificate
    // ========================================================================

    let certificate: acm.ICertificate | undefined;

    if (props.customDomainName) {
      const acmCertificate = new acm.Certificate(
        this,
        "PlanningDomainCertificate",
        {
          domainName: props.customDomainName,
          validation: acm.CertificateValidation.fromDns(
            props.hostedZoneId
              ? route53.HostedZone.fromHostedZoneAttributes(
                  this,
                  "HostedZone",
                  {
                    hostedZoneId: props.hostedZoneId,
                    zoneName: props.customDomainName,
                  },
                )
              : undefined,
          ),
        },
      );
      cdk.Tags.of(acmCertificate).add("Environment", env);
      cdk.Tags.of(acmCertificate).add("Project", "ELS-Planning");
      certificate = acmCertificate;
    }

    // ========================================================================
    // Frontend Distribution (S3 + CloudFront + OAC)
    // ========================================================================

    const frontend = new FrontendDistribution(this, "PlanningFrontend", {
      environmentName: env,
      projectTag: "ELS-Planning",
      bucketPrefix: "els-planning-frontend",
      apiGateway: apiGateway,
      customDomainName: props.customDomainName,
      hostedZoneId: props.hostedZoneId,
      certificate: certificate,
      cfnLogicalIds: {
        bucket: "PlanningFrontendBucket",
        oac: "PlanningCloudFrontOAC",
        distribution: "PlanningCloudFrontDistribution",
        bucketPolicy: "PlanningFrontendBucketPolicy",
      },
    });

    // ========================================================================
    // Conditional Custom Domain: Route53 Alias Record
    // ========================================================================

    if (props.customDomainName && props.hostedZoneId) {
      new route53.CfnRecordSet(this, "PlanningDnsRecord", {
        hostedZoneId: props.hostedZoneId,
        name: props.customDomainName,
        type: "A",
        aliasTarget: {
          dnsName: frontend.distribution.attrDomainName,
          hostedZoneId: "Z2FDTNDATAQYW2", // CloudFront global hosted zone ID
          evaluateTargetHealth: false,
        },
      });
    }

    // ========================================================================
    // Bedrock Guardrail
    // ========================================================================

    const guardrail = new bedrock.CfnGuardrail(
      this,
      "PlanningBedrockGuardrail",
      {
        name: `els-planning-guardrail-${env}`,
        description: "Guardrails for the Parent Planning Tool Bedrock Agent",
        blockedInputMessaging:
          "I'm sorry, but I can only help with creating and refining learning plans for your child. Could you please ask me something related to your child's learning plan?",
        blockedOutputsMessaging:
          "I'm sorry, but I'm unable to provide that type of response. I'm here to help you create and refine learning plans for your child. Let's get back to planning!",
        contentPolicyConfig: {
          filtersConfig: [
            {
              type: "SEXUAL",
              inputStrength: "HIGH",
              outputStrength: "HIGH",
            },
            {
              type: "VIOLENCE",
              inputStrength: "HIGH",
              outputStrength: "HIGH",
            },
            {
              type: "HATE",
              inputStrength: "HIGH",
              outputStrength: "HIGH",
            },
            {
              type: "INSULTS",
              inputStrength: "HIGH",
              outputStrength: "HIGH",
            },
            {
              type: "MISCONDUCT",
              inputStrength: "HIGH",
              outputStrength: "HIGH",
            },
            {
              type: "PROMPT_ATTACK",
              inputStrength: "HIGH",
              outputStrength: "NONE",
            },
          ],
        },
        topicPolicyConfig: {
          topicsConfig: [
            {
              name: "MedicalAdvice",
              definition:
                "Prescribing medication, drug dosages, or clinical treatment plans. Excludes educational learning domains like physical development, motor skills, or social emotional learning.",
              examples: [
                "What medication should I give my child for ADHD?",
                "What dosage of melatonin is safe for a 3-year-old?",
                "Should I try an elimination diet to treat my child's behavior?",
                "Can you prescribe something for my child's anxiety?",
              ],
              type: "DENY",
            },
            {
              name: "ClinicalDiagnosis",
              definition:
                "Diagnosing medical conditions, disabilities, or disorders like autism, ADHD, or dyslexia. Excludes discussing educational developmental domains or age-appropriate milestones.",
              examples: [
                "Does my child have autism?",
                "Can you diagnose my child with ADHD?",
                "My child isn't talking yet, do they have a speech disorder?",
                "Is my child developmentally delayed?",
              ],
              type: "DENY",
            },
            {
              name: "TherapyRecommendations",
              definition:
                "Recommending clinical therapies like ABA, occupational therapy, speech therapy, or counseling. Excludes educational activities supporting motor skills or social emotional learning.",
              examples: [
                "Should my child start ABA therapy?",
                "Do you recommend occupational therapy for my toddler?",
                "What type of speech therapy is best for a 4-year-old?",
                "Can you refer us to a behavioral therapist?",
              ],
              type: "DENY",
            },
            {
              name: "Politics",
              definition:
                "Discussing political parties, elections, candidates, or partisan policies. Excludes referencing state early learning standards or education frameworks.",
              examples: [
                "What do you think about the current president?",
                "Which political party supports early childhood education?",
                "What is your opinion on school voucher legislation?",
                "Should I vote for the candidate who supports pre-K funding?",
              ],
              type: "DENY",
            },
            {
              name: "Religion",
              definition:
                "Promoting or discussing specific religious beliefs, doctrines, religious practices, or faith-based parenting philosophies.",
              examples: [
                "What does the Bible say about raising children?",
                "Should I teach my child to pray?",
                "Which religion has the best approach to early education?",
                "Can you include Bible verses in the learning plan?",
              ],
              type: "DENY",
            },
            {
              name: "PersonalRelationships",
              definition:
                "Providing advice on marital issues, romantic relationships, family conflicts, co-parenting disputes, custody matters, or interpersonal relationship counseling.",
              examples: [
                "My spouse and I disagree on parenting, what should I do?",
                "How do I handle my ex's parenting style?",
                "I'm going through a divorce, how will it affect my child?",
                "My mother-in-law undermines my parenting decisions.",
              ],
              type: "DENY",
            },
            {
              name: "FinancialAdvice",
              definition:
                "Providing financial planning advice, investment recommendations, budgeting guidance, cost comparisons of educational programs, or monetary planning.",
              examples: [
                "How much should I save for my child's college?",
                "Is private preschool worth the cost?",
                "What's the best 529 plan for education savings?",
                "How do I budget for childcare expenses?",
              ],
              type: "DENY",
            },
            {
              name: "LegalAdvice",
              definition:
                "Providing legal advice, interpreting laws, advising on custody arrangements, special education legal rights (IEP/504 disputes), or any guidance that should come from a licensed attorney.",
              examples: [
                "What are my legal rights for an IEP meeting?",
                "Can I sue the school for not accommodating my child?",
                "How do I file for custody of my child?",
                "Is it legal for the daycare to do that?",
              ],
              type: "DENY",
            },
            {
              name: "HarmToChildren",
              definition:
                "Any content that describes, encourages, or normalizes physical punishment, emotional abuse, neglect, or any form of harm to children.",
              examples: [
                "Is it okay to spank my child when they misbehave?",
                "How do I discipline my child physically?",
                "My child needs to learn the hard way.",
                "Sometimes kids need to be scared into behaving.",
              ],
              type: "DENY",
            },
          ],
        },
        sensitiveInformationPolicyConfig: {
          piiEntitiesConfig: [
            { type: "EMAIL", action: "BLOCK" },
            { type: "PHONE", action: "BLOCK" },
            { type: "NAME", action: "ANONYMIZE" },
            { type: "US_SOCIAL_SECURITY_NUMBER", action: "BLOCK" },
            { type: "CREDIT_DEBIT_CARD_NUMBER", action: "BLOCK" },
            { type: "US_BANK_ACCOUNT_NUMBER", action: "BLOCK" },
            { type: "US_BANK_ROUTING_NUMBER", action: "BLOCK" },
            { type: "IP_ADDRESS", action: "BLOCK" },
            { type: "URL", action: "BLOCK" },
            { type: "DRIVER_ID", action: "BLOCK" },
            { type: "US_PASSPORT_NUMBER", action: "BLOCK" },
            {
              type: "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER",
              action: "BLOCK",
            },
            { type: "INTERNATIONAL_BANK_ACCOUNT_NUMBER", action: "BLOCK" },
            { type: "SWIFT_CODE", action: "BLOCK" },
            { type: "CA_HEALTH_NUMBER", action: "BLOCK" },
            { type: "CA_SOCIAL_INSURANCE_NUMBER", action: "BLOCK" },
            { type: "UK_NATIONAL_INSURANCE_NUMBER", action: "BLOCK" },
            { type: "PIN", action: "BLOCK" },
            { type: "PASSWORD", action: "BLOCK" },
            { type: "AWS_ACCESS_KEY", action: "BLOCK" },
            { type: "AWS_SECRET_KEY", action: "BLOCK" },
          ],
          regexesConfig: [
            {
              name: "EmailPattern",
              description: "Matches email addresses",
              pattern: "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}",
              action: "BLOCK",
            },
            {
              name: "PhonePattern",
              description: "Matches US phone numbers",
              pattern:
                "(\\+?1[-\\s.]?)?\\(?\\d{3}\\)?[-\\s.]?\\d{3}[-\\s.]?\\d{4}",
              action: "BLOCK",
            },
            {
              name: "SSNPattern",
              description: "Matches US Social Security Numbers",
              pattern: "\\b\\d{3}[-\\s]?\\d{2}[-\\s]?\\d{4}\\b",
              action: "BLOCK",
            },
            {
              name: "DateOfBirthPattern",
              description:
                "Matches common date of birth formats (MM/DD/YYYY, MM-DD-YYYY)",
              pattern:
                "\\b(0[1-9]|1[0-2])[/\\-](0[1-9]|[12]\\d|3[01])[/\\-](19|20)\\d{2}\\b",
              action: "BLOCK",
            },
            {
              name: "StreetAddressPattern",
              description: "Matches common US street address patterns",
              pattern:
                "\\b\\d{1,5}\\s[A-Za-z]+\\s(St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Ct|Court|Way|Pl|Place)\\b",
              action: "BLOCK",
            },
          ],
        },
        wordPolicyConfig: {
          managedWordListsConfig: [{ type: "PROFANITY" }],
        },
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Planning" },
        ],
      },
    );

    // ========================================================================
    // Bedrock Guardrail Version
    // ========================================================================

    const guardrailVersion = new bedrock.CfnGuardrailVersion(
      this,
      "PlanningBedrockGuardrailVersion",
      {
        guardrailIdentifier: guardrail.ref,
        description: `Planning guardrail version - ${env}`,
      },
    );

    // ========================================================================
    // AgentCore Runtime (direct code deploy)
    // ========================================================================

    // Resolve agent code path relative to the CDK project root (infra/cdk).
    // Using process.cwd() because __dirname differs between source (lib/) and
    // compiled output (dist/lib/), but cdk commands always run from infra/cdk.
    const agentCodePath = path.resolve(
      process.cwd(),
      "../../packages/agentcore-agent",
    );

    const agentRuntimeArtifact = agentcore.AgentRuntimeArtifact.fromCodeAsset({
      path: agentCodePath,
      runtime: agentcore.AgentCoreRuntime.PYTHON_3_13,
      entrypoint: ["app.py"],
      exclude: [
        ".venv",
        "__pycache__",
        "*.pyc",
        ".hypothesis",
        ".pytest_cache",
        ".bedrock_agentcore",
        "tests",
      ],
    });

    const agentRuntime = new agentcore.Runtime(this, "PlanningAgentRuntime", {
      runtimeName: `els_planning_agent_${env}`,
      agentRuntimeArtifact: agentRuntimeArtifact,
      protocolConfiguration: agentcore.ProtocolType.HTTP,
      environmentVariables: {
        DB_CLUSTER_ARN: databaseClusterArn,
        DB_SECRET_ARN: databaseSecretArn,
        DB_NAME: "els_pipeline",
        GUARDRAIL_ID: guardrail.ref,
        GUARDRAIL_VERSION: guardrailVersion.attrVersion,
      },
      tags: {
        Environment: env,
        Project: "ELS-Planning",
      },
    });

    // Grant the runtime permissions for Bedrock model invocation
    agentRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "BedrockModelInvocation",
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          `arn:aws:bedrock:*::foundation-model/*`,
          `arn:aws:bedrock:${region}:${accountId}:inference-profile/*`,
        ],
      }),
    );

    // Bedrock Guardrail Access
    agentRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "BedrockGuardrailAccess",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:ApplyGuardrail"],
        resources: [guardrail.attrGuardrailArn],
      }),
    );

    // RDS Data API Access
    agentRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "RdsDataApiAccess",
        effect: iam.Effect.ALLOW,
        actions: [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement",
        ],
        resources: [databaseClusterArn],
      }),
    );

    // Secrets Manager Access
    agentRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SecretsManagerAccess",
        effect: iam.Effect.ALLOW,
        actions: ["secretsmanager:GetSecretValue"],
        resources: [databaseSecretArn],
      }),
    );

    // CloudWatch Logs Access
    agentRuntime.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "CloudWatchLogsAccess",
        effect: iam.Effect.ALLOW,
        actions: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ],
        resources: [
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/bedrock-agentcore/*`,
        ],
      }),
    );

    // Wire the runtime ARN into the Lambda function's environment
    // (CfnFunction doesn't support addEnvironment, so we use an override)
    const cfnLambda = planningApiLambdaFunction;
    cfnLambda.addPropertyOverride(
      "Environment.Variables.AGENTCORE_RUNTIME_ARN",
      agentRuntime.agentRuntimeArn,
    );

    // Grant the Lambda permission to invoke the AgentCore runtime
    const planningApiLambdaRoleL2 = iam.Role.fromRoleArn(
      this,
      "PlanningApiLambdaRoleRef",
      planningApiLambdaRole.attrArn,
    );
    agentRuntime.grantInvokeRuntime(planningApiLambdaRoleL2);

    // ========================================================================
    // Outputs
    // ========================================================================

    new cdk.CfnOutput(this, "PlanningFrontendBucketName", {
      value: frontend.bucket.bucketName,
      description: "S3 bucket for planning frontend static assets",
    });

    new cdk.CfnOutput(this, "PlanningCloudFrontDomainName", {
      value: frontend.distribution.attrDomainName,
      description: "CloudFront distribution URL for the planning site",
    });

    new cdk.CfnOutput(this, "PlanningCloudFrontDistributionId", {
      value: frontend.distribution.ref,
      description: "CloudFront distribution ID (for cache invalidation)",
    });

    new cdk.CfnOutput(this, "PlanningApiGatewayUrl", {
      value: `https://${apiGateway.ref}.execute-api.${region}.amazonaws.com`,
      description: "Planning API Gateway endpoint URL",
    });

    new cdk.CfnOutput(this, "PlanningApiLambdaFunctionName", {
      value: planningApiLambdaFunction.ref,
      description: "Planning API Lambda function name",
    });

    new cdk.CfnOutput(this, "PlanningGuardrailId", {
      value: guardrail.ref,
      description: "Bedrock Guardrail ID",
    });

    new cdk.CfnOutput(this, "PlanningGuardrailVersion", {
      value: guardrailVersion.attrVersion,
      description: "Bedrock Guardrail version number",
    });

    new cdk.CfnOutput(this, "PlanningAgentCoreRuntimeArn", {
      value: agentRuntime.agentRuntimeArn,
      description: "AgentCore Runtime ARN (managed by CDK)",
    });

    new cdk.CfnOutput(this, "PlanningAgentCoreRoleArn", {
      value: agentRuntime.role.roleArn,
      description: "IAM role ARN for the AgentCore Runtime agent",
    });

    if (props.customDomainName) {
      new cdk.CfnOutput(this, "PlanningCustomDomainUrl", {
        value: `https://${props.customDomainName}`,
        description: "Custom domain URL for the planning site",
      });
    }
  }
}
