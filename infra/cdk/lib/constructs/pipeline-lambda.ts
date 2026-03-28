import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export interface PipelineLambdaProps {
  functionName: string;
  handler: string;
  role: iam.IRole;
  timeout: cdk.Duration;
  memorySize: number;
  environment: Record<string, string>;
  /**
   * Absolute or relative path to the Python source directory.
   * CDK will bundle this with Docker (pip install + copy source) and
   * content-hash the result so CloudFormation updates the function
   * whenever the code actually changes.
   */
  codePath: string;
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

    this.function = new lambda.Function(this, "Function", {
      functionName: props.functionName,
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: props.handler,
      role: props.role,
      timeout: props.timeout,
      memorySize: props.memorySize,
      environment: props.environment,
      code: lambda.Code.fromAsset(props.codePath, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            "bash",
            "-c",
            [
              "pip install boto3 pydantic psycopg2-binary python-dotenv -t /asset-output --quiet",
              "cp -au . /asset-output",
            ].join(" && "),
          ],
        },
      }),
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
