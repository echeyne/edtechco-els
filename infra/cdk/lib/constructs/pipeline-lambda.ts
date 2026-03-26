import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export interface PipelineLambdaProps {
  functionName: string;
  handler: string;
  role: iam.IRole;
  timeout: cdk.Duration;
  memorySize: number;
  environment: Record<string, string>;
  codeBucket: string;
  codeKey: string;
  cfnLogicalId?: string;
  vpcConfig?: {
    vpc: ec2.IVpc;
    securityGroups: ec2.ISecurityGroup[];
    subnets: ec2.ISubnet[];
  };
}

export class PipelineLambda extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: PipelineLambdaProps) {
    super(scope, id);

    const codeBucket = s3.Bucket.fromBucketName(
      this,
      "CodeBucket",
      props.codeBucket,
    );

    this.function = new lambda.Function(this, "Function", {
      functionName: props.functionName,
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: props.handler,
      role: props.role,
      timeout: props.timeout,
      memorySize: props.memorySize,
      environment: props.environment,
      code: lambda.Code.fromBucket(codeBucket, props.codeKey),
      ...(props.vpcConfig && {
        vpc: props.vpcConfig.vpc,
        securityGroups: props.vpcConfig.securityGroups,
        vpcSubnets: { subnets: props.vpcConfig.subnets },
      }),
    });

    // Override the nested logical ID to match the original CloudFormation template.
    // CDK nests this as <ConstructId>Function<Hash> but the original template uses
    // <ConstructId>Function as the logical ID at the stack level.
    if (props.cfnLogicalId) {
      (this.function.node.defaultChild as cdk.CfnResource).overrideLogicalId(
        props.cfnLogicalId,
      );
    }

    cdk.Tags.of(this.function).add(
      "Environment",
      props.environment["ENVIRONMENT"] || "dev",
    );
    cdk.Tags.of(this.function).add("Project", "ELS-Pipeline");
  }
}
