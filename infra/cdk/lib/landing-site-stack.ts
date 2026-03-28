import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as iam from "aws-cdk-lib/aws-iam";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import { Construct } from "constructs";

export interface LandingSiteStackProps extends cdk.StackProps {
  environmentName: string;
  customDomainName?: string;
  hostedZoneId?: string;
}

export class LandingSiteStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: LandingSiteStackProps) {
    super(scope, id, props);

    const env = props.environmentName;
    const accountId = cdk.Aws.ACCOUNT_ID;

    // ========================================================================
    // S3 Bucket for landing site static assets
    // ========================================================================

    const bucket = new s3.Bucket(this, "LandingSiteBucket", {
      bucketName: `els-landing-site-${env}-${accountId}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
    });
    cdk.Tags.of(bucket).add("Environment", env);
    cdk.Tags.of(bucket).add("Project", "ELS-LandingSite");

    // ========================================================================
    // CloudFront Origin Access Control
    // ========================================================================

    const oac = new cloudfront.CfnOriginAccessControl(this, "LandingSiteOAC", {
      originAccessControlConfig: {
        name: `els-landing-site-oac-${env}-${cdk.Aws.STACK_NAME}`,
        originAccessControlOriginType: "s3",
        signingBehavior: "always",
        signingProtocol: "sigv4",
      },
    });

    // ========================================================================
    // Conditional Custom Domain: ACM Certificate
    // ========================================================================

    let certificate: acm.ICertificate | undefined;

    if (props.customDomainName) {
      const acmCertificate = new acm.Certificate(
        this,
        "LandingSiteCertificate",
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
      cdk.Tags.of(acmCertificate).add("Project", "ELS-LandingSite");
      certificate = acmCertificate;
    }

    // ========================================================================
    // CloudFront Distribution (S3 origin only — no API Gateway)
    // ========================================================================

    const s3Origin: cloudfront.CfnDistribution.OriginProperty = {
      id: "S3Origin",
      domainName: bucket.bucketRegionalDomainName,
      originAccessControlId: oac.attrId,
      s3OriginConfig: {
        originAccessIdentity: "",
      },
    };

    const distributionConfig: cloudfront.CfnDistribution.DistributionConfigProperty =
      {
        enabled: true,
        comment: `ELS-LandingSite - ${env}`,
        defaultRootObject: "index.html",
        httpVersion: "http2and3",
        origins: [s3Origin],
        defaultCacheBehavior: {
          targetOriginId: "S3Origin",
          viewerProtocolPolicy: "redirect-to-https",
          cachePolicyId: "658327ea-f89d-4fab-a63d-7e88639e58f6", // CachingOptimized
          compress: true,
        },
        customErrorResponses: [
          {
            errorCode: 403,
            responseCode: 200,
            responsePagePath: "/index.html",
            errorCachingMinTtl: 0,
          },
          {
            errorCode: 404,
            responseCode: 200,
            responsePagePath: "/index.html",
            errorCachingMinTtl: 0,
          },
        ],
        // Conditional custom domain aliases and certificate
        ...(props.customDomainName && certificate
          ? {
              aliases: [props.customDomainName],
              viewerCertificate: {
                acmCertificateArn: certificate.certificateArn,
                sslSupportMethod: "sni-only",
                minimumProtocolVersion: "TLSv1.2_2021",
              },
            }
          : {}),
      };

    const distribution = new cloudfront.CfnDistribution(
      this,
      "LandingSiteDistribution",
      {
        distributionConfig,
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-LandingSite" },
        ],
      },
    );

    // ========================================================================
    // S3 Bucket Policy granting CloudFront OAC read access
    // ========================================================================

    const bucketPolicy = new s3.BucketPolicy(this, "LandingSiteBucketPolicy", {
      bucket: bucket,
    });

    bucketPolicy.document.addStatements(
      new iam.PolicyStatement({
        sid: "AllowCloudFrontOAC",
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("cloudfront.amazonaws.com")],
        actions: ["s3:GetObject"],
        resources: [`${bucket.bucketArn}/*`],
        conditions: {
          StringEquals: {
            "AWS:SourceArn": `arn:aws:cloudfront::${accountId}:distribution/${distribution.attrId}`,
          },
        },
      }),
    );

    // ========================================================================
    // Conditional Custom Domain: Route 53 A-Record Alias
    // ========================================================================

    if (props.customDomainName && props.hostedZoneId) {
      new route53.CfnRecordSet(this, "LandingSiteDnsRecord", {
        hostedZoneId: props.hostedZoneId,
        name: props.customDomainName,
        type: "A",
        aliasTarget: {
          dnsName: distribution.attrDomainName,
          hostedZoneId: "Z2FDTNDATAQYW2", // CloudFront global hosted zone ID
          evaluateTargetHealth: false,
        },
      });
    }

    // ========================================================================
    // Stack Outputs
    // ========================================================================

    new cdk.CfnOutput(this, "LandingSiteBucketName", {
      value: bucket.bucketName,
      description: "S3 bucket for landing site static assets",
    });

    new cdk.CfnOutput(this, "LandingSiteCloudFrontDomainName", {
      value: distribution.attrDomainName,
      description: "CloudFront distribution domain for the landing site",
    });

    new cdk.CfnOutput(this, "LandingSiteCloudFrontDistributionId", {
      value: distribution.ref,
      description: "CloudFront distribution ID (for cache invalidation)",
    });

    if (props.customDomainName) {
      new cdk.CfnOutput(this, "LandingSiteCustomDomainUrl", {
        value: `https://${props.customDomainName}`,
        description: "Custom domain URL for the landing site",
      });
    }
  }
}
