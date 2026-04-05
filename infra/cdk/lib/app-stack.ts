import * as path from "path";
import * as cdk from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import { Construct } from "constructs";
import { FrontendDistribution } from "./constructs/frontend-distribution";

export interface ElsAppStackProps extends cdk.StackProps {
  environmentName: string;
  pipelineStackName: string;
  descopeProjectId: string;
  customDomainName?: string;
  hostedZoneId?: string;
}

export class ElsAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ElsAppStackProps) {
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
    // API Lambda IAM Role (CfnRole L1 to match original CFN template)
    // ========================================================================

    const apiLambdaRole = new iam.CfnRole(this, "ApiLambdaRole", {
      roleName: `els-api-lambda-role-${env}`,
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
          policyName: "S3Access",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "S3Access",
                Effect: "Allow",
                Action: ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                Resource: [
                  `arn:aws:s3:::els-raw-documents-${env}-${accountId}`,
                  `arn:aws:s3:::els-raw-documents-${env}-${accountId}/*`,
                  `arn:aws:s3:::els-processed-json-${env}-${accountId}`,
                  `arn:aws:s3:::els-processed-json-${env}-${accountId}/*`,
                ],
              },
            ],
          },
        },
        {
          policyName: "RdsDataAccess",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "RdsDataAccess",
                Effect: "Allow",
                Action: [
                  "rds-data:ExecuteStatement",
                  "rds-data:BatchExecuteStatement",
                  "rds-data:BeginTransaction",
                  "rds-data:CommitTransaction",
                  "rds-data:RollbackTransaction",
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
        { key: "Project", value: "ELS-App" },
      ],
    });

    // ========================================================================
    // API Lambda Function
    // ========================================================================

    // Resolve the API source directory relative to the CDK project root.
    // CDK bundles this with esbuild and content-hashes the result, so
    // CloudFormation updates the function whenever the code changes.
    const apiCodePath = path.resolve(
      process.cwd(),
      "../../packages/els-explorer-api",
    );

    const apiLambdaFunction = new lambda.Function(this, "ApiLambdaFunction", {
      functionName: `els-api-${env}`,
      runtime: lambda.Runtime.NODEJS_22_X,
      handler: "index.handler",
      role: iam.Role.fromRoleArn(
        this,
        "ApiLambdaRoleRef",
        apiLambdaRole.attrArn,
      ),
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      environment: {
        ENVIRONMENT: env,
        DB_CLUSTER_ARN: databaseClusterArn,
        DB_SECRET_ARN: databaseSecretArn,
        DB_NAME: "els_pipeline",
        ELS_RAW_BUCKET: `els-raw-documents-${env}-${accountId}`,
        ELS_PROCESSED_BUCKET: `els-processed-json-${env}-${accountId}`,
        DESCOPE_PROJECT_ID: props.descopeProjectId,
      },
      code: lambda.Code.fromAsset(apiCodePath, {
        bundling: {
          image: lambda.Runtime.NODEJS_22_X.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              try {
                const { execSync } = require("child_process");
                execSync(
                  [
                    "npx esbuild src/lambda.ts",
                    "--bundle",
                    "--platform=node",
                    "--target=node22",
                    "--format=esm",
                    `--outfile=${outputDir}/index.mjs`,
                    "--external:@aws-sdk/*",
                    "'--banner:js=import { createRequire } from \"module\"; const require = createRequire(import.meta.url);'",
                  ].join(" "),
                  {
                    cwd: apiCodePath,
                    stdio: ["ignore", "pipe", "inherit"],
                  },
                );
                return true;
              } catch {
                return false;
              }
            },
          },
          command: [
            "bash",
            "-c",
            [
              "mkdir -p /tmp/build",
              "cp package.json /tmp/build/",
              "npm install --prefix /tmp/build",
              "npx --prefix /tmp/build esbuild src/lambda.ts --bundle --platform=node --target=node22 --format=esm --outfile=/asset-output/index.mjs --external:@aws-sdk/* '--banner:js=import { createRequire } from \"module\"; const require = createRequire(import.meta.url);'",
            ].join(" && "),
          ],
          environment: {
            // Ensure npm can write to tmp
            HOME: "/tmp",
          },
        },
      }),
    });
    (apiLambdaFunction.node.defaultChild as cdk.CfnResource).overrideLogicalId(
      "ApiLambdaFunction",
    );
    cdk.Tags.of(apiLambdaFunction).add("Environment", env);
    cdk.Tags.of(apiLambdaFunction).add("Project", "ELS-App");

    // ========================================================================
    // HTTP API Gateway (L1 constructs matching CloudFormation)
    // ========================================================================

    const apiGateway = new apigatewayv2.CfnApi(this, "ApiGateway", {
      name: `els-api-${env}`,
      protocolType: "HTTP",
      // CORS is handled by the Lambda (Hono cors() middleware) rather than
      // at the API Gateway level. This avoids a circular CloudFormation
      // dependency: CloudFront references the API Gateway endpoint for its
      // origin, so the API Gateway cannot also reference the CloudFront
      // domain for CORS allow-origins.
    });

    const apiGatewayIntegration = new apigatewayv2.CfnIntegration(
      this,
      "ApiGatewayIntegration",
      {
        apiId: apiGateway.ref,
        integrationType: "AWS_PROXY",
        integrationUri: apiLambdaFunction.functionArn,
        payloadFormatVersion: "2.0",
      },
    );

    new apigatewayv2.CfnRoute(this, "ApiGatewayRoute", {
      apiId: apiGateway.ref,
      routeKey: "$default",
      target: `integrations/${apiGatewayIntegration.ref}`,
    });

    new apigatewayv2.CfnStage(this, "ApiGatewayStage", {
      apiId: apiGateway.ref,
      stageName: "$default",
      autoDeploy: true,
    });

    // Lambda permission for API Gateway invocation
    new lambda.CfnPermission(this, "ApiLambdaPermission", {
      functionName: apiLambdaFunction.functionName,
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
        "CustomDomainCertificate",
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
      cdk.Tags.of(acmCertificate).add("Project", "ELS-App");
      certificate = acmCertificate;
    }

    // ========================================================================
    // Frontend Distribution (S3 + CloudFront + OAC)
    // ========================================================================

    const frontend = new FrontendDistribution(this, "Frontend", {
      environmentName: env,
      projectTag: "ELS-App",
      bucketPrefix: "els-frontend",
      apiGateway: apiGateway,
      customDomainName: props.customDomainName,
      hostedZoneId: props.hostedZoneId,
      certificate: certificate,
      cfnLogicalIds: {
        bucket: "FrontendBucket",
        oac: "CloudFrontOAC",
        distribution: "CloudFrontDistribution",
        bucketPolicy: "FrontendBucketPolicy",
      },
    });

    // Note: CORS allow-origins (including the CloudFront domain) are handled
    // by the Lambda's Hono cors() middleware, not the API Gateway.

    // ========================================================================
    // Conditional Custom Domain: Route53 Alias Record
    // ========================================================================

    if (props.customDomainName && props.hostedZoneId) {
      new route53.CfnRecordSet(this, "DnsRecord", {
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
    // Outputs
    // ========================================================================

    new cdk.CfnOutput(this, "FrontendBucketName", {
      value: frontend.bucket.bucketName,
      description: "S3 bucket for frontend static assets",
    });

    new cdk.CfnOutput(this, "CloudFrontDomainName", {
      value: frontend.distribution.attrDomainName,
      description: "CloudFront distribution URL",
    });

    new cdk.CfnOutput(this, "CloudFrontDistributionId", {
      value: frontend.distribution.ref,
      description: "CloudFront distribution ID (for cache invalidation)",
    });

    new cdk.CfnOutput(this, "ApiGatewayUrl", {
      value: `https://${apiGateway.ref}.execute-api.${region}.amazonaws.com`,
      description: "API Gateway endpoint URL",
    });

    new cdk.CfnOutput(this, "ApiLambdaFunctionName", {
      value: apiLambdaFunction.functionName,
    });

    if (props.customDomainName) {
      new cdk.CfnOutput(this, "CustomDomainUrl", {
        value: `https://${props.customDomainName}`,
        description: "Custom domain URL for the frontend",
      });
    }
  }
}
