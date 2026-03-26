import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import { ElsAppStack } from "../lib/app-stack";

describe("ElsAppStack", () => {
  describe("without custom domain", () => {
    let template: Template;

    beforeAll(() => {
      const app = new cdk.App();
      const stack = new ElsAppStack(app, "TestAppStack", {
        environmentName: "dev",
        pipelineStackName: "els-pipeline-dev",
        descopeProjectId: "test-descope-id",
        env: { region: "us-east-1", account: "123456789012" },
      });
      template = Template.fromStack(stack);
    });

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

    test("CloudFront distribution exists", () => {
      template.resourceCountIs("AWS::CloudFront::Distribution", 1);
    });

    test("Lambda function uses nodejs22.x runtime", () => {
      template.hasResourceProperties("AWS::Lambda::Function", {
        Runtime: "nodejs22.x",
      });
    });

    test("HTTP API Gateway exists", () => {
      template.hasResourceProperties("AWS::ApiGatewayV2::Api", {
        ProtocolType: "HTTP",
      });
    });

    test("no ACM Certificate resources", () => {
      template.resourceCountIs("AWS::CertificateManager::Certificate", 0);
    });

    test("no Route53 RecordSet resources", () => {
      template.resourceCountIs("AWS::Route53::RecordSet", 0);
    });

    test("outputs FrontendBucketName", () => {
      template.hasOutput("FrontendBucketName", {});
    });

    test("outputs CloudFrontDomainName", () => {
      template.hasOutput("CloudFrontDomainName", {});
    });

    test("outputs CloudFrontDistributionId", () => {
      template.hasOutput("CloudFrontDistributionId", {});
    });

    test("outputs ApiGatewayUrl", () => {
      template.hasOutput("ApiGatewayUrl", {});
    });

    test("outputs ApiLambdaFunctionName", () => {
      template.hasOutput("ApiLambdaFunctionName", {});
    });
  });

  describe("with custom domain", () => {
    let template: Template;

    beforeAll(() => {
      const app = new cdk.App();
      const stack = new ElsAppStack(app, "TestAppStackDomain", {
        environmentName: "dev",
        pipelineStackName: "els-pipeline-dev",
        descopeProjectId: "test-descope-id",
        customDomainName: "app.example.com",
        hostedZoneId: "Z1234567890",
        env: { region: "us-east-1", account: "123456789012" },
      });
      template = Template.fromStack(stack);
    });

    test("ACM Certificate exists", () => {
      template.resourceCountIs("AWS::CertificateManager::Certificate", 1);
    });

    test("Route53 RecordSet exists", () => {
      template.resourceCountIs("AWS::Route53::RecordSet", 1);
    });

    test("outputs CustomDomainUrl", () => {
      template.hasOutput("CustomDomainUrl", {});
    });
  });
});
