import * as cdk from "aws-cdk-lib";
import { Template, Match } from "aws-cdk-lib/assertions";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as iam from "aws-cdk-lib/aws-iam";
import { FrontendDistribution } from "../lib/constructs/frontend-distribution";
import { PipelineLambda } from "../lib/constructs/pipeline-lambda";

describe("FrontendDistribution construct", () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new cdk.Stack(app, "TestFrontendStack", {
      env: { region: "us-east-1", account: "123456789012" },
    });

    // Create a mock CfnApi to pass as apiGateway prop
    const api = new apigatewayv2.CfnApi(stack, "MockApi", {
      name: "test-api",
      protocolType: "HTTP",
    });

    new FrontendDistribution(stack, "TestFrontend", {
      environmentName: "dev",
      projectTag: "TestProject",
      bucketPrefix: "test-frontend",
      apiGateway: api,
    });

    template = Template.fromStack(stack);
  });

  test("creates S3 bucket with public access blocked", () => {
    template.hasResourceProperties("AWS::S3::Bucket", {
      PublicAccessBlockConfiguration: {
        BlockPublicAcls: true,
        BlockPublicPolicy: true,
        IgnorePublicAcls: true,
        RestrictPublicBuckets: true,
      },
    });
  });

  test("creates S3 bucket with S3-managed encryption", () => {
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

  test("creates CloudFront distribution", () => {
    template.resourceCountIs("AWS::CloudFront::Distribution", 1);
  });

  test("creates CloudFront OAC", () => {
    template.hasResourceProperties("AWS::CloudFront::OriginAccessControl", {
      OriginAccessControlConfig: {
        OriginAccessControlOriginType: "s3",
        SigningBehavior: "always",
        SigningProtocol: "sigv4",
      },
    });
  });

  test("creates S3 bucket policy", () => {
    template.hasResourceProperties("AWS::S3::BucketPolicy", {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Effect: "Allow",
            Principal: {
              Service: "cloudfront.amazonaws.com",
            },
            Action: "s3:GetObject",
          }),
        ]),
      },
    });
  });
});

describe("PipelineLambda construct", () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new cdk.Stack(app, "TestPipelineLambdaStack", {
      env: { region: "us-east-1", account: "123456789012" },
    });

    const role = new iam.Role(stack, "TestRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
    });

    new PipelineLambda(stack, "TestLambda", {
      functionName: "test-lambda-fn",
      handler: "handler.main",
      role: role,
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        ENVIRONMENT: "dev",
        TEST_VAR: "value",
      },
      codeBucket: "test-code-bucket",
      codeKey: "test-code.zip",
    });

    template = Template.fromStack(stack);
  });

  test("creates Lambda function with Python 3.13 runtime", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      Runtime: "python3.13",
    });
  });

  test("Lambda function has correct name", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      FunctionName: "test-lambda-fn",
    });
  });

  test("Lambda function has correct handler", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      Handler: "handler.main",
    });
  });

  test("Lambda function has correct timeout", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      Timeout: 60,
    });
  });

  test("Lambda function has correct memory", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      MemorySize: 512,
    });
  });
});
