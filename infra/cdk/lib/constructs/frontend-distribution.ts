import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as iam from "aws-cdk-lib/aws-iam";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import { Construct } from "constructs";

export interface FrontendDistributionProps {
  environmentName: string;
  projectTag: string;
  bucketPrefix: string;
  apiGateway: apigatewayv2.CfnApi;
  customDomainName?: string;
  hostedZoneId?: string;
  certificate?: acm.ICertificate;
  /** Override logical IDs to match an existing CloudFormation template for migration. */
  cfnLogicalIds?: {
    bucket: string;
    oac: string;
    distribution: string;
    bucketPolicy: string;
  };
}

export class FrontendDistribution extends Construct {
  public readonly bucket: s3.Bucket;
  public readonly distribution: cloudfront.CfnDistribution;

  constructor(scope: Construct, id: string, props: FrontendDistributionProps) {
    super(scope, id);

    const accountId = cdk.Stack.of(this).account;

    // ─── S3 Bucket for frontend static assets ───
    this.bucket = new s3.Bucket(this, "Bucket", {
      bucketName: `${props.bucketPrefix}-${props.environmentName}-${accountId}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
    });
    cdk.Tags.of(this.bucket).add("Environment", props.environmentName);
    cdk.Tags.of(this.bucket).add("Project", props.projectTag);
    if (props.cfnLogicalIds?.bucket) {
      (this.bucket.node.defaultChild as cdk.CfnResource).overrideLogicalId(
        props.cfnLogicalIds.bucket,
      );
    }

    // ─── CloudFront Origin Access Control ───
    const oacName = `${props.bucketPrefix}-oac-${props.environmentName}-${cdk.Aws.STACK_NAME}`;
    const oac = new cloudfront.CfnOriginAccessControl(this, "OAC", {
      originAccessControlConfig: {
        name: oacName,
        originAccessControlOriginType: "s3",
        signingBehavior: "always",
        signingProtocol: "sigv4",
      },
    });
    if (props.cfnLogicalIds?.oac) {
      oac.overrideLogicalId(props.cfnLogicalIds.oac);
    }

    // ─── Build origins ───
    const s3Origin: cloudfront.CfnDistribution.OriginProperty = {
      id: "S3Origin",
      domainName: this.bucket.bucketRegionalDomainName,
      originAccessControlId: oac.attrId,
      s3OriginConfig: {
        originAccessIdentity: "",
      },
    };

    const apiOrigin: cloudfront.CfnDistribution.OriginProperty = {
      id: "ApiOrigin",
      domainName: cdk.Fn.select(
        2,
        cdk.Fn.split("/", props.apiGateway.attrApiEndpoint),
      ),
      customOriginConfig: {
        httpsPort: 443,
        originProtocolPolicy: "https-only",
      },
    };

    // ─── Build distribution config ───
    const distributionConfig: cloudfront.CfnDistribution.DistributionConfigProperty =
      {
        enabled: true,
        comment: `${props.projectTag} - ${props.environmentName}`,
        defaultRootObject: "index.html",
        httpVersion: "http2and3",
        origins: [s3Origin, apiOrigin],
        defaultCacheBehavior: {
          targetOriginId: "S3Origin",
          viewerProtocolPolicy: "redirect-to-https",
          cachePolicyId: "658327ea-f89d-4fab-a63d-7e88639e58f6", // CachingOptimized
          compress: true,
        },
        cacheBehaviors: [
          {
            pathPattern: "/api/*",
            targetOriginId: "ApiOrigin",
            viewerProtocolPolicy: "redirect-to-https",
            cachePolicyId: "4135ea2d-6df8-44a3-9df3-4b5a84be39ad", // CachingDisabled
            originRequestPolicyId: "b689b0a8-53d0-40ab-baf2-68738e2966ac", // AllViewerExceptHostHeader
            allowedMethods: [
              "GET",
              "HEAD",
              "OPTIONS",
              "PUT",
              "PATCH",
              "POST",
              "DELETE",
            ],
          },
        ],
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
        ...(props.customDomainName && props.certificate
          ? {
              aliases: [props.customDomainName],
              viewerCertificate: {
                acmCertificateArn: props.certificate.certificateArn,
                sslSupportMethod: "sni-only",
                minimumProtocolVersion: "TLSv1.2_2021",
              },
            }
          : {}),
      };

    this.distribution = new cloudfront.CfnDistribution(this, "Distribution", {
      distributionConfig,
      tags: [
        { key: "Environment", value: props.environmentName },
        { key: "Project", value: props.projectTag },
      ],
    });
    if (props.cfnLogicalIds?.distribution) {
      this.distribution.overrideLogicalId(props.cfnLogicalIds.distribution);
    }

    // ─── S3 Bucket Policy granting CloudFront OAC access only ───
    const bucketPolicy = new s3.BucketPolicy(this, "BucketPolicy", {
      bucket: this.bucket,
    });
    if (props.cfnLogicalIds?.bucketPolicy) {
      (bucketPolicy.node.defaultChild as cdk.CfnResource).overrideLogicalId(
        props.cfnLogicalIds.bucketPolicy,
      );
    }

    bucketPolicy.document.addStatements(
      new iam.PolicyStatement({
        sid: "AllowCloudFrontOAC",
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("cloudfront.amazonaws.com")],
        actions: ["s3:GetObject"],
        resources: [`${this.bucket.bucketArn}/*`],
        conditions: {
          StringEquals: {
            "AWS:SourceArn": `arn:aws:cloudfront::${accountId}:distribution/${this.distribution.attrId}`,
          },
        },
      }),
    );
  }
}
