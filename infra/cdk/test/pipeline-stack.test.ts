import * as cdk from "aws-cdk-lib";
import { Template, Match } from "aws-cdk-lib/assertions";
import { ElsPipelineStack } from "../lib/pipeline-stack";

describe("ElsPipelineStack", () => {
  let template: Template;
  const stackName = "TestPipelineStack";

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new ElsPipelineStack(app, stackName, {
      environmentName: "dev",
      env: { region: "us-east-1", account: "123456789012" },
    });
    template = Template.fromStack(stack);
  });

  // ── S3 Buckets ──

  test("creates 2 S3 buckets", () => {
    template.resourceCountIs("AWS::S3::Bucket", 2);
  });

  test("S3 buckets have versioning enabled", () => {
    template.hasResourceProperties("AWS::S3::Bucket", {
      VersioningConfiguration: { Status: "Enabled" },
    });
  });

  test("S3 buckets have public access blocked", () => {
    template.hasResourceProperties("AWS::S3::Bucket", {
      PublicAccessBlockConfiguration: {
        BlockPublicAcls: true,
        BlockPublicPolicy: true,
        IgnorePublicAcls: true,
        RestrictPublicBuckets: true,
      },
    });
  });

  test("S3 buckets have S3-managed encryption", () => {
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

  // ── VPC and Networking ──

  test("VPC has correct CIDR", () => {
    template.hasResourceProperties("AWS::EC2::VPC", {
      CidrBlock: "10.0.0.0/16",
    });
  });

  test("creates 2 subnets with correct CIDRs", () => {
    template.hasResourceProperties("AWS::EC2::Subnet", {
      CidrBlock: "10.0.1.0/24",
    });
    template.hasResourceProperties("AWS::EC2::Subnet", {
      CidrBlock: "10.0.2.0/24",
    });
  });

  // ── Aurora Cluster ──

  test("Aurora cluster uses PostgreSQL engine", () => {
    template.hasResourceProperties("AWS::RDS::DBCluster", {
      Engine: "aurora-postgresql",
      EngineVersion: "15.15",
      DatabaseName: "els_pipeline",
    });
  });

  test("Aurora cluster has serverless v2 scaling", () => {
    template.hasResourceProperties("AWS::RDS::DBCluster", {
      ServerlessV2ScalingConfiguration: {
        MinCapacity: 0.5,
        MaxCapacity: 2,
      },
    });
  });

  // ── Lambda Functions ──

  test("creates 12 Lambda functions", () => {
    template.resourceCountIs("AWS::Lambda::Function", 12);
  });

  test("Lambda functions use Python 3.13 runtime", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      Runtime: "python3.13",
    });
  });

  // ── Step Functions ──

  test("creates 1 Step Functions state machine", () => {
    template.resourceCountIs("AWS::StepFunctions::StateMachine", 1);
  });

  // ── SNS ──

  test("creates 1 SNS topic", () => {
    template.resourceCountIs("AWS::SNS::Topic", 1);
  });

  // ── Cross-Stack Exports ──

  test("exports EnvironmentName", () => {
    template.hasOutput("EnvironmentName", {
      Export: { Name: `${stackName}-EnvironmentName` },
    });
  });

  test("exports Region", () => {
    template.hasOutput("Region", {
      Export: { Name: `${stackName}-Region` },
    });
  });

  test("exports RawDocumentsBucket", () => {
    template.hasOutput("RawDocumentsBucketName", {
      Export: { Name: `${stackName}-RawDocumentsBucket` },
    });
  });

  test("exports RawDocumentsBucketArn", () => {
    template.hasOutput("RawDocumentsBucketArn", {
      Export: { Name: `${stackName}-RawDocumentsBucketArn` },
    });
  });

  test("exports ProcessedJsonBucket", () => {
    template.hasOutput("ProcessedJsonBucketName", {
      Export: { Name: `${stackName}-ProcessedJsonBucket` },
    });
  });

  test("exports ProcessedJsonBucketArn", () => {
    template.hasOutput("ProcessedJsonBucketArn", {
      Export: { Name: `${stackName}-ProcessedJsonBucketArn` },
    });
  });

  test("exports DatabaseClusterArn", () => {
    template.hasOutput("DatabaseClusterArn", {
      Export: { Name: `${stackName}-DatabaseClusterArn` },
    });
  });

  test("exports DatabaseSecretArn", () => {
    template.hasOutput("DatabaseSecretArn", {
      Export: { Name: `${stackName}-DatabaseSecretArn` },
    });
  });

  test("exports DatabaseVPCId", () => {
    template.hasOutput("DatabaseVPCId", {
      Export: { Name: `${stackName}-DatabaseVPCId` },
    });
  });

  test("exports LambdaSecurityGroupId", () => {
    template.hasOutput("LambdaSecurityGroupId", {
      Export: { Name: `${stackName}-LambdaSecurityGroupId` },
    });
  });

  test("exports DatabaseSubnet1Id", () => {
    template.hasOutput("DatabaseSubnet1Id", {
      Export: { Name: `${stackName}-DatabaseSubnet1Id` },
    });
  });

  test("exports DatabaseSubnet2Id", () => {
    template.hasOutput("DatabaseSubnet2Id", {
      Export: { Name: `${stackName}-DatabaseSubnet2Id` },
    });
  });

  test("exports PipelineStateMachineArn", () => {
    template.hasOutput("PipelineStateMachineArn", {
      Export: { Name: `${stackName}-PipelineStateMachineArn` },
    });
  });

  test("exports PipelineNotificationTopicArn", () => {
    template.hasOutput("PipelineNotificationTopicArn", {
      Export: { Name: `${stackName}-PipelineNotificationTopicArn` },
    });
  });

  test("exports StepFunctionsExecutionRoleArn", () => {
    template.hasOutput("StepFunctionsExecutionRoleArn", {
      Export: { Name: `${stackName}-StepFunctionsExecutionRoleArn` },
    });
  });

  test("exports PipelineLogGroupName", () => {
    template.hasOutput("PipelineLogGroupName", {
      Export: { Name: `${stackName}-PipelineLogGroupName` },
    });
  });
});
