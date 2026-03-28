import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import { LandingSiteStack } from "../lib/landing-site-stack";

describe("LandingSiteStack", () => {
  describe("without custom domain", () => {
    let template: Template;

    beforeAll(() => {
      const app = new cdk.App();
      const stack = new LandingSiteStack(app, "TestLandingSiteStack", {
        environmentName: "dev",
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

    test("CloudFront has default root object index.html", () => {
      template.hasResourceProperties("AWS::CloudFront::Distribution", {
        DistributionConfig: {
          DefaultRootObject: "index.html",
        },
      });
    });

    test("CloudFront has HTTP to HTTPS redirect", () => {
      template.hasResourceProperties("AWS::CloudFront::Distribution", {
        DistributionConfig: {
          DefaultCacheBehavior: {
            ViewerProtocolPolicy: "redirect-to-https",
          },
        },
      });
    });

    test("CloudFront has custom error responses for 403 and 404", () => {
      template.hasResourceProperties("AWS::CloudFront::Distribution", {
        DistributionConfig: {
          CustomErrorResponses: [
            {
              ErrorCode: 403,
              ResponseCode: 200,
              ResponsePagePath: "/index.html",
              ErrorCachingMinTTL: 0,
            },
            {
              ErrorCode: 404,
              ResponseCode: 200,
              ResponsePagePath: "/index.html",
              ErrorCachingMinTTL: 0,
            },
          ],
        },
      });
    });

    // ── No API Gateway or Lambda ──

    test("no API Gateway resources", () => {
      template.resourceCountIs("AWS::ApiGatewayV2::Api", 0);
    });

    test("no Lambda resources", () => {
      template.resourceCountIs("AWS::Lambda::Function", 0);
    });

    // ── Conditional: no custom domain ──

    test("no ACM Certificate resources", () => {
      template.resourceCountIs("AWS::CertificateManager::Certificate", 0);
    });

    test("no Route53 RecordSet resources", () => {
      template.resourceCountIs("AWS::Route53::RecordSet", 0);
    });

    // ── Outputs ──

    test("outputs LandingSiteBucketName", () => {
      template.hasOutput("LandingSiteBucketName", {});
    });

    test("outputs LandingSiteCloudFrontDomainName", () => {
      template.hasOutput("LandingSiteCloudFrontDomainName", {});
    });

    test("outputs LandingSiteCloudFrontDistributionId", () => {
      template.hasOutput("LandingSiteCloudFrontDistributionId", {});
    });
  });

  describe("with custom domain", () => {
    let template: Template;

    beforeAll(() => {
      const app = new cdk.App();
      const stack = new LandingSiteStack(app, "TestLandingSiteStackDomain", {
        environmentName: "dev",
        customDomainName: "landing.example.com",
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

    test("outputs LandingSiteCustomDomainUrl", () => {
      template.hasOutput("LandingSiteCustomDomainUrl", {});
    });
  });
});
