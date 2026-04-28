import * as path from "path";
import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as iam from "aws-cdk-lib/aws-iam";
import * as sns from "aws-cdk-lib/aws-sns";
import * as logs from "aws-cdk-lib/aws-logs";
import * as sfn from "aws-cdk-lib/aws-stepfunctions";
import * as ssm from "aws-cdk-lib/aws-ssm";
import { Construct } from "constructs";
import { PipelineLambda } from "./constructs/pipeline-lambda";

export interface ElsPipelineStackProps extends cdk.StackProps {
  environmentName: string;
}

export class ElsPipelineStack extends cdk.Stack {
  public readonly rawDocumentsBucket: s3.Bucket;
  public readonly processedJsonBucket: s3.Bucket;
  public readonly vpc: ec2.CfnVPC;
  public readonly databaseSubnet1: ec2.CfnSubnet;
  public readonly databaseSubnet2: ec2.CfnSubnet;
  public readonly lambdaSecurityGroup: ec2.CfnSecurityGroup;
  public readonly databaseCluster: rds.CfnDBCluster;
  public readonly databaseSecret: secretsmanager.CfnSecret;

  constructor(scope: Construct, id: string, props: ElsPipelineStackProps) {
    super(scope, id, props);

    const env = props.environmentName;
    const accountId = cdk.Aws.ACCOUNT_ID;
    const region = cdk.Aws.REGION;

    // ========================================================================
    // S3 Buckets
    // ========================================================================

    this.rawDocumentsBucket = new s3.Bucket(this, "RawDocumentsBucket", {
      bucketName: `els-raw-documents-${env}-${accountId}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });
    (
      this.rawDocumentsBucket.node.defaultChild as cdk.CfnResource
    ).overrideLogicalId("RawDocumentsBucket");
    cdk.Tags.of(this.rawDocumentsBucket).add("Environment", env);
    cdk.Tags.of(this.rawDocumentsBucket).add("Project", "ELS-Pipeline");

    this.processedJsonBucket = new s3.Bucket(this, "ProcessedJsonBucket", {
      bucketName: `els-processed-json-${env}-${accountId}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });
    (
      this.processedJsonBucket.node.defaultChild as cdk.CfnResource
    ).overrideLogicalId("ProcessedJsonBucket");
    cdk.Tags.of(this.processedJsonBucket).add("Environment", env);
    cdk.Tags.of(this.processedJsonBucket).add("Project", "ELS-Pipeline");

    // ========================================================================
    // VPC and Networking
    // ========================================================================

    this.vpc = new ec2.CfnVPC(this, "DatabaseVPC", {
      cidrBlock: "10.0.0.0/16",
      enableDnsHostnames: true,
      enableDnsSupport: true,
      tags: [
        { key: "Name", value: `els-database-vpc-${env}` },
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    this.databaseSubnet1 = new ec2.CfnSubnet(this, "DatabaseSubnet1", {
      vpcId: this.vpc.ref,
      cidrBlock: "10.0.1.0/24",
      availabilityZone: cdk.Fn.select(0, cdk.Fn.getAzs("")),
      tags: [
        { key: "Name", value: `els-database-subnet-1-${env}` },
        { key: "Environment", value: env },
      ],
    });

    this.databaseSubnet2 = new ec2.CfnSubnet(this, "DatabaseSubnet2", {
      vpcId: this.vpc.ref,
      cidrBlock: "10.0.2.0/24",
      availabilityZone: cdk.Fn.select(1, cdk.Fn.getAzs("")),
      tags: [
        { key: "Name", value: `els-database-subnet-2-${env}` },
        { key: "Environment", value: env },
      ],
    });

    const dbSubnetGroup = new rds.CfnDBSubnetGroup(
      this,
      "DatabaseSubnetGroup",
      {
        dbSubnetGroupName: `els-database-subnet-group-${env}`,
        dbSubnetGroupDescription:
          "Subnet group for ELS Aurora PostgreSQL cluster",
        subnetIds: [this.databaseSubnet1.ref, this.databaseSubnet2.ref],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    // Security Groups
    const databaseSecurityGroup = new ec2.CfnSecurityGroup(
      this,
      "DatabaseSecurityGroup",
      {
        groupName: `els-database-sg-${env}`,
        groupDescription: "Security group for ELS Aurora PostgreSQL cluster",
        vpcId: this.vpc.ref,
        tags: [
          { key: "Name", value: `els-database-sg-${env}` },
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    this.lambdaSecurityGroup = new ec2.CfnSecurityGroup(
      this,
      "LambdaSecurityGroup",
      {
        groupName: `els-lambda-sg-${env}`,
        groupDescription:
          "Security group for Lambda functions accessing Aurora",
        vpcId: this.vpc.ref,
        securityGroupEgress: [
          {
            ipProtocol: "tcp",
            fromPort: 443,
            toPort: 443,
            cidrIp: "0.0.0.0/0",
            description: "Allow HTTPS for AWS API calls",
          },
        ],
        tags: [
          { key: "Name", value: `els-lambda-sg-${env}` },
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const vpcEndpointSecurityGroup = new ec2.CfnSecurityGroup(
      this,
      "VpcEndpointSecurityGroup",
      {
        groupName: `els-vpce-sg-${env}`,
        groupDescription: "Security group for VPC Interface Endpoints",
        vpcId: this.vpc.ref,
        securityGroupIngress: [
          {
            ipProtocol: "tcp",
            fromPort: 443,
            toPort: 443,
            sourceSecurityGroupId: this.lambdaSecurityGroup.attrGroupId,
            description: "Allow HTTPS from Lambda functions",
          },
        ],
        tags: [
          { key: "Name", value: `els-vpce-sg-${env}` },
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    // Security Group Ingress/Egress rules
    new ec2.CfnSecurityGroupIngress(this, "DatabaseSecurityGroupIngress", {
      groupId: databaseSecurityGroup.attrGroupId,
      ipProtocol: "tcp",
      fromPort: 5432,
      toPort: 5432,
      sourceSecurityGroupId: this.lambdaSecurityGroup.attrGroupId,
      description: "Allow PostgreSQL access from Lambda functions",
    });

    new ec2.CfnSecurityGroupEgress(this, "LambdaSecurityGroupEgress", {
      groupId: this.lambdaSecurityGroup.attrGroupId,
      ipProtocol: "tcp",
      fromPort: 5432,
      toPort: 5432,
      destinationSecurityGroupId: databaseSecurityGroup.attrGroupId,
      description: "Allow PostgreSQL access to Aurora",
    });

    // Route Table
    const privateRouteTable = new ec2.CfnRouteTable(this, "PrivateRouteTable", {
      vpcId: this.vpc.ref,
      tags: [
        { key: "Name", value: `els-private-rt-${env}` },
        { key: "Environment", value: env },
      ],
    });

    new ec2.CfnSubnetRouteTableAssociation(
      this,
      "PrivateSubnet1RouteTableAssociation",
      {
        subnetId: this.databaseSubnet1.ref,
        routeTableId: privateRouteTable.ref,
      },
    );

    new ec2.CfnSubnetRouteTableAssociation(
      this,
      "PrivateSubnet2RouteTableAssociation",
      {
        subnetId: this.databaseSubnet2.ref,
        routeTableId: privateRouteTable.ref,
      },
    );

    // VPC Endpoints
    new ec2.CfnVPCEndpoint(this, "S3VpcEndpoint", {
      vpcId: this.vpc.ref,
      serviceName: `com.amazonaws.${region}.s3`,
      vpcEndpointType: "Gateway",
      routeTableIds: [privateRouteTable.ref],
    });

    new ec2.CfnVPCEndpoint(this, "SecretsManagerVpcEndpoint", {
      vpcId: this.vpc.ref,
      serviceName: `com.amazonaws.${region}.secretsmanager`,
      vpcEndpointType: "Interface",
      privateDnsEnabled: true,
      subnetIds: [this.databaseSubnet1.ref, this.databaseSubnet2.ref],
      securityGroupIds: [vpcEndpointSecurityGroup.attrGroupId],
    });

    // ========================================================================
    // Aurora PostgreSQL
    // ========================================================================

    this.databaseSecret = new secretsmanager.CfnSecret(this, "DatabaseSecret", {
      name: `els-database-credentials-${env}`,
      description: "Database credentials for ELS Aurora PostgreSQL cluster",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: "els_admin" }),
        generateStringKey: "password",
        passwordLength: 32,
        excludeCharacters: '"@/\\',
      },
      tags: [
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    this.databaseCluster = new rds.CfnDBCluster(this, "DatabaseCluster", {
      dbClusterIdentifier: `els-database-cluster-${env}`,
      engine: "aurora-postgresql",
      engineVersion: "15.15",
      databaseName: "els_pipeline",
      masterUsername: `{{resolve:secretsmanager:${this.databaseSecret.ref}:SecretString:username}}`,
      masterUserPassword: `{{resolve:secretsmanager:${this.databaseSecret.ref}:SecretString:password}}`,
      dbSubnetGroupName: dbSubnetGroup.ref,
      vpcSecurityGroupIds: [databaseSecurityGroup.attrGroupId],
      serverlessV2ScalingConfiguration: {
        minCapacity: 0.5,
        maxCapacity: 2,
      },
      backupRetentionPeriod: 7,
      preferredBackupWindow: "03:00-04:00",
      preferredMaintenanceWindow: "sun:04:00-sun:05:00",
      enableCloudwatchLogsExports: ["postgresql"],
      enableHttpEndpoint: true,
      tags: [
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    new rds.CfnDBInstance(this, "DatabaseInstance", {
      dbInstanceIdentifier: `els-database-instance-${env}`,
      dbClusterIdentifier: this.databaseCluster.ref,
      dbInstanceClass: "db.serverless",
      engine: "aurora-postgresql",
      publiclyAccessible: false,
      tags: [
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    new secretsmanager.CfnSecretTargetAttachment(
      this,
      "DatabaseSecretAttachment",
      {
        secretId: this.databaseSecret.ref,
        targetId: this.databaseCluster.ref,
        targetType: "AWS::RDS::DBCluster",
      },
    );

    // ========================================================================
    // IAM Roles for Lambda Functions (CfnRole L1 to match original CFN template)
    // ========================================================================

    const lambdaAssumeRolePolicy = {
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Principal: { Service: "lambda.amazonaws.com" },
          Action: "sts:AssumeRole",
        },
      ],
    };

    const rawBucketArn = this.rawDocumentsBucket.bucketArn;
    const processedBucketArn = this.processedJsonBucket.bucketArn;

    const ingesterLambdaRole = new iam.CfnRole(this, "IngesterLambdaRole", {
      roleName: `els-ingester-lambda-role-${env}`,
      assumeRolePolicyDocument: lambdaAssumeRolePolicy,
      managedPolicyArns: [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
      ],
      policies: [
        {
          policyName: "S3RawBucketAccess",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Effect: "Allow",
                Action: [
                  "s3:PutObject",
                  "s3:PutObjectTagging",
                  "s3:GetObject",
                  "s3:GetObjectVersion",
                ],
                Resource: `${rawBucketArn}/*`,
              },
              {
                Effect: "Allow",
                Action: ["s3:ListBucket", "s3:ListBucketVersions"],
                Resource: rawBucketArn,
              },
            ],
          },
        },
      ],
      tags: [
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    const textExtractorLambdaRole = new iam.CfnRole(
      this,
      "TextExtractorLambdaRole",
      {
        roleName: `els-text-extractor-lambda-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3RawBucketReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: [
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:HeadObject",
                  ],
                  Resource: `${rawBucketArn}/*`,
                },
                {
                  Effect: "Allow",
                  Action: ["s3:ListBucket", "s3:ListBucketVersions"],
                  Resource: rawBucketArn,
                },
              ],
            },
          },
          {
            policyName: "S3ProcessedBucketWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/extraction/*`,
                },
              ],
            },
          },
          {
            policyName: "TextractAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: [
                    "textract:DetectDocumentText",
                    "textract:AnalyzeDocument",
                    "textract:StartDocumentTextDetection",
                    "textract:GetDocumentTextDetection",
                    "textract:StartDocumentAnalysis",
                    "textract:GetDocumentAnalysis",
                  ],
                  Resource: "*",
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const structureDetectorLambdaRole = new iam.CfnRole(
      this,
      "StructureDetectorLambdaRole",
      {
        roleName: `els-structure-detector-lambda-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3ExtractionReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/extraction/*`,
                },
              ],
            },
          },
          {
            policyName: "S3DetectionWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
          {
            policyName: "BedrockInvokeAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["bedrock:InvokeModel"],
                  Resource: "*",
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const hierarchyParserLambdaRole = new iam.CfnRole(
      this,
      "HierarchyParserLambdaRole",
      {
        roleName: `els-hierarchy-parser-lambda-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3DetectionReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
          {
            policyName: "S3ParsingWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
                },
              ],
            },
          },
          {
            policyName: "BedrockInvokeAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["bedrock:InvokeModel"],
                  Resource: "*",
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const detectionBatchPreparerLambdaRole = new iam.CfnRole(
      this,
      "DetectionBatchPreparerLambdaRole",
      {
        roleName: `els-detection-batch-preparer-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3ExtractionReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/extraction/*`,
                },
              ],
            },
          },
          {
            policyName: "S3DetectionBatchWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const detectionBatchProcessorLambdaRole = new iam.CfnRole(
      this,
      "DetectionBatchProcessorLambdaRole",
      {
        roleName: `els-detection-batch-processor-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3DetectionBatchReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
          {
            policyName: "S3DetectionResultWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
          {
            policyName: "BedrockInvokeAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["bedrock:InvokeModel"],
                  Resource: "*",
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const detectionMergerLambdaRole = new iam.CfnRole(
      this,
      "DetectionMergerLambdaRole",
      {
        roleName: `els-detection-merger-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3DetectionReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
          {
            policyName: "S3DetectionOutputWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const parseBatchPreparerLambdaRole = new iam.CfnRole(
      this,
      "ParseBatchPreparerLambdaRole",
      {
        roleName: `els-parse-batch-preparer-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3DetectionOutputReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/detection/*`,
                },
              ],
            },
          },
          {
            policyName: "S3ParsingBatchWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const parseBatchProcessorLambdaRole = new iam.CfnRole(
      this,
      "ParseBatchProcessorLambdaRole",
      {
        roleName: `els-parse-batch-processor-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3ParsingBatchReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
                },
              ],
            },
          },
          {
            policyName: "S3ParsingResultWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
                },
              ],
            },
          },
          {
            policyName: "BedrockInvokeAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["bedrock:InvokeModel"],
                  Resource: "*",
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const parseMergerLambdaRole = new iam.CfnRole(
      this,
      "ParseMergerLambdaRole",
      {
        roleName: `els-parse-merger-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        ],
        policies: [
          {
            policyName: "S3ParsingReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
                },
              ],
            },
          },
          {
            policyName: "S3ParsingOutputWriteAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:PutObject"],
                  Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    const validatorLambdaRole = new iam.CfnRole(this, "ValidatorLambdaRole", {
      roleName: `els-validator-lambda-role-${env}`,
      assumeRolePolicyDocument: lambdaAssumeRolePolicy,
      managedPolicyArns: [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
      ],
      policies: [
        {
          policyName: "S3ParsingReadAccess",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Effect: "Allow",
                Action: ["s3:GetObject"],
                Resource: `${processedBucketArn}/*/intermediate/parsing/*`,
              },
            ],
          },
        },
        {
          policyName: "S3ProcessedBucketAccess",
          policyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Effect: "Allow",
                Action: ["s3:PutObject", "s3:GetObject", "s3:GetObjectVersion"],
                Resource: `${processedBucketArn}/*`,
              },
              {
                Effect: "Allow",
                Action: ["s3:ListBucket"],
                Resource: processedBucketArn,
              },
            ],
          },
        },
      ],
      tags: [
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    const persistenceLambdaRole = new iam.CfnRole(
      this,
      "PersistenceLambdaRole",
      {
        roleName: `els-persistence-lambda-role-${env}`,
        assumeRolePolicyDocument: lambdaAssumeRolePolicy,
        managedPolicyArns: [
          "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
          "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
        ],
        policies: [
          {
            policyName: "RDSDataAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: [
                    "rds-data:ExecuteStatement",
                    "rds-data:BatchExecuteStatement",
                    "rds-data:BeginTransaction",
                    "rds-data:CommitTransaction",
                    "rds-data:RollbackTransaction",
                  ],
                  Resource: `arn:aws:rds:${region}:${accountId}:cluster:*`,
                },
                {
                  Effect: "Allow",
                  Action: ["secretsmanager:GetSecretValue"],
                  Resource: this.databaseSecret.ref,
                },
              ],
            },
          },
          {
            policyName: "S3ProcessedBucketReadAccess",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["s3:GetObject"],
                  Resource: `${processedBucketArn}/*`,
                },
                {
                  Effect: "Allow",
                  Action: ["s3:ListBucket"],
                  Resource: processedBucketArn,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    // ========================================================================
    // Lambda Functions
    // ========================================================================

    // Resolve the Python source directory relative to the CDK project root.
    // CDK bundles this with Docker (pip install + copy) and content-hashes
    // the result, so CloudFormation updates the function whenever code changes.
    const pipelineCodePath = path.resolve(process.cwd(), "../../src");

    // Wrap CfnRoles as IRole for PipelineLambda construct
    const wrapRole = (cfnRole: iam.CfnRole): iam.IRole =>
      iam.Role.fromRoleArn(this, `${cfnRole.node.id}Ref`, cfnRole.attrArn);

    // We need an L2 VPC reference for the PipelineLambda construct's vpcConfig
    const l2Vpc = ec2.Vpc.fromVpcAttributes(this, "ImportedVpc", {
      vpcId: this.vpc.ref,
      availabilityZones: [
        cdk.Fn.select(0, cdk.Fn.getAzs("")),
        cdk.Fn.select(1, cdk.Fn.getAzs("")),
      ],
    });
    const l2LambdaSg = ec2.SecurityGroup.fromSecurityGroupId(
      this,
      "ImportedLambdaSg",
      this.lambdaSecurityGroup.attrGroupId,
    );
    const l2Subnet1 = ec2.Subnet.fromSubnetAttributes(this, "ImportedSubnet1", {
      subnetId: this.databaseSubnet1.ref,
      availabilityZone: cdk.Fn.select(0, cdk.Fn.getAzs("")),
    });
    const l2Subnet2 = ec2.Subnet.fromSubnetAttributes(this, "ImportedSubnet2", {
      subnetId: this.databaseSubnet2.ref,
      availabilityZone: cdk.Fn.select(1, cdk.Fn.getAzs("")),
    });

    const ingesterLambda = new PipelineLambda(this, "IngesterLambda", {
      functionName: `els-ingester-${env}`,
      handler: "els_pipeline.handlers.ingestion_handler",
      role: wrapRole(ingesterLambdaRole),
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        ELS_RAW_BUCKET: this.rawDocumentsBucket.bucketName,
        ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
        ENVIRONMENT: env,
        COUNTRY_CODE_VALIDATION: "enabled",
      },
      codePath: pipelineCodePath,
      cfnLogicalId: "IngesterLambdaFunction",
    });

    const textExtractorLambda = new PipelineLambda(
      this,
      "TextExtractorLambda",
      {
        functionName: `els-text-extractor-${env}`,
        handler: "els_pipeline.handlers.extraction_handler",
        role: wrapRole(textExtractorLambdaRole),
        timeout: cdk.Duration.seconds(300),
        memorySize: 1024,
        environment: {
          ELS_RAW_BUCKET: this.rawDocumentsBucket.bucketName,
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          ENVIRONMENT: env,
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "TextExtractorLambdaFunction",
      },
    );

    const structureDetectorLambda = new PipelineLambda(
      this,
      "StructureDetectorLambda",
      {
        functionName: `els-structure-detector-${env}`,
        handler: "els_pipeline.handlers.detection_handler",
        role: wrapRole(structureDetectorLambdaRole),
        timeout: cdk.Duration.seconds(900),
        memorySize: 1024,
        environment: {
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          BEDROCK_DETECTOR_LLM_MODEL_ID: "us.anthropic.claude-opus-4-7",
          CONFIDENCE_THRESHOLD: "0.7",
          ENVIRONMENT: env,
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "StructureDetectorLambdaFunction",
      },
    );

    const hierarchyParserLambda = new PipelineLambda(
      this,
      "HierarchyParserLambda",
      {
        functionName: `els-hierarchy-parser-${env}`,
        handler: "els_pipeline.handlers.parsing_handler",
        role: wrapRole(hierarchyParserLambdaRole),
        timeout: cdk.Duration.seconds(900),
        memorySize: 1024,
        environment: {
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          ENVIRONMENT: env,
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "HierarchyParserLambdaFunction",
      },
    );

    const prepareDetectionBatchesLambda = new PipelineLambda(
      this,
      "PrepareDetectionBatchesLambda",
      {
        functionName: `els-prepare-detection-batches-${env}`,
        handler: "els_pipeline.handlers.prepare_detection_batches_handler",
        role: wrapRole(detectionBatchPreparerLambdaRole),
        timeout: cdk.Duration.seconds(60),
        memorySize: 512,
        environment: {
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          ENVIRONMENT: env,
          MAX_CHUNKS_PER_BATCH: "5",
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "PrepareDetectionBatchesLambdaFunction",
      },
    );

    const detectBatchLambda = new PipelineLambda(this, "DetectBatchLambda", {
      functionName: `els-detect-batch-${env}`,
      handler: "els_pipeline.handlers.detect_batch_handler",
      role: wrapRole(detectionBatchProcessorLambdaRole),
      timeout: cdk.Duration.seconds(900),
      memorySize: 1024,
      environment: {
        ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
        BEDROCK_DETECTOR_LLM_MODEL_ID: "us.anthropic.claude-opus-4-7",
        CONFIDENCE_THRESHOLD: "0.7",
        MAX_CHUNKS_PER_BATCH: "5",
        ENVIRONMENT: env,
      },
      codePath: pipelineCodePath,
      cfnLogicalId: "DetectBatchLambdaFunction",
    });

    const mergeDetectionResultsLambda = new PipelineLambda(
      this,
      "MergeDetectionResultsLambda",
      {
        functionName: `els-merge-detection-results-${env}`,
        handler: "els_pipeline.handlers.merge_detection_results_handler",
        role: wrapRole(detectionMergerLambdaRole),
        timeout: cdk.Duration.seconds(120),
        memorySize: 512,
        environment: {
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          CONFIDENCE_THRESHOLD: "0.7",
          ENVIRONMENT: env,
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "MergeDetectionResultsLambdaFunction",
      },
    );

    const prepareParseBatchesLambda = new PipelineLambda(
      this,
      "PrepareParseBatchesLambda",
      {
        functionName: `els-prepare-parse-batches-${env}`,
        handler: "els_pipeline.handlers.prepare_parse_batches_handler",
        role: wrapRole(parseBatchPreparerLambdaRole),
        timeout: cdk.Duration.seconds(60),
        memorySize: 512,
        environment: {
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          ENVIRONMENT: env,
          MAX_DOMAINS_PER_BATCH: "3",
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "PrepareParseBatchesLambdaFunction",
      },
    );

    const parseBatchLambda = new PipelineLambda(this, "ParseBatchLambda", {
      functionName: `els-parse-batch-${env}`,
      handler: "els_pipeline.handlers.parse_batch_handler",
      role: wrapRole(parseBatchProcessorLambdaRole),
      timeout: cdk.Duration.seconds(900),
      memorySize: 1024,
      environment: {
        ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
        ENVIRONMENT: env,
        MAX_DOMAINS_PER_BATCH: "3",
      },
      codePath: pipelineCodePath,
      cfnLogicalId: "ParseBatchLambdaFunction",
    });

    const mergeParseResultsLambda = new PipelineLambda(
      this,
      "MergeParseResultsLambda",
      {
        functionName: `els-merge-parse-results-${env}`,
        handler: "els_pipeline.handlers.merge_parse_results_handler",
        role: wrapRole(parseMergerLambdaRole),
        timeout: cdk.Duration.seconds(120),
        memorySize: 512,
        environment: {
          ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
          ENVIRONMENT: env,
        },
        codePath: pipelineCodePath,
        cfnLogicalId: "MergeParseResultsLambdaFunction",
      },
    );

    const validatorLambda = new PipelineLambda(this, "ValidatorLambda", {
      functionName: `els-validator-${env}`,
      handler: "els_pipeline.handlers.validation_handler",
      role: wrapRole(validatorLambdaRole),
      timeout: cdk.Duration.seconds(180),
      memorySize: 512,
      environment: {
        ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
        ENVIRONMENT: env,
      },
      codePath: pipelineCodePath,
      cfnLogicalId: "ValidatorLambdaFunction",
    });

    const persistenceLambda = new PipelineLambda(this, "PersistenceLambda", {
      functionName: `els-persistence-${env}`,
      handler: "els_pipeline.handlers.persistence_handler",
      role: wrapRole(persistenceLambdaRole),
      timeout: cdk.Duration.seconds(180),
      memorySize: 512,
      environment: {
        ELS_PROCESSED_BUCKET: this.processedJsonBucket.bucketName,
        DB_SECRET_ARN: this.databaseSecret.ref,
        DB_CLUSTER_ARN: `arn:aws:rds:${region}:${accountId}:cluster:${this.databaseCluster.ref}`,
        ENVIRONMENT: env,
      },
      codePath: pipelineCodePath,
      cfnLogicalId: "PersistenceLambdaFunction",
      vpcConfig: {
        vpc: l2Vpc,
        securityGroups: [l2LambdaSg],
        subnets: [l2Subnet1, l2Subnet2],
      },
    });

    // ========================================================================
    // SNS and CloudWatch
    // ========================================================================

    const notificationTopic = new sns.Topic(this, "PipelineNotificationTopic", {
      topicName: `els-pipeline-notifications-${env}`,
      displayName: "ELS Pipeline Notifications",
    });
    (notificationTopic.node.defaultChild as cdk.CfnResource).overrideLogicalId(
      "PipelineNotificationTopic",
    );
    cdk.Tags.of(notificationTopic).add("Environment", env);
    cdk.Tags.of(notificationTopic).add("Project", "ELS-Pipeline");

    const pipelineLogGroup = new logs.LogGroup(this, "PipelineLogGroup", {
      logGroupName: `/aws/vendedlogs/states/els-pipeline-${env}`,
      retention: logs.RetentionDays.ONE_MONTH,
    });
    (pipelineLogGroup.node.defaultChild as cdk.CfnResource).overrideLogicalId(
      "PipelineLogGroup",
    );

    // ========================================================================
    // Step Functions Execution Role (CfnRole L1 to match original CFN template)
    // ========================================================================

    const stepFunctionsExecutionRole = new iam.CfnRole(
      this,
      "StepFunctionsExecutionRole",
      {
        roleName: `els-step-functions-role-${env}`,
        assumeRolePolicyDocument: {
          Version: "2012-10-17",
          Statement: [
            {
              Effect: "Allow",
              Principal: { Service: "states.amazonaws.com" },
              Action: "sts:AssumeRole",
            },
          ],
        },
        policies: [
          {
            policyName: "LambdaInvokePolicy",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["lambda:InvokeFunction"],
                  Resource: `arn:aws:lambda:${region}:${accountId}:function:els-*-${env}`,
                },
              ],
            },
          },
          {
            policyName: "SNSPublishPolicy",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: ["sns:Publish"],
                  Resource: notificationTopic.topicArn,
                },
              ],
            },
          },
          {
            policyName: "CloudWatchLogsPolicy",
            policyDocument: {
              Version: "2012-10-17",
              Statement: [
                {
                  Effect: "Allow",
                  Action: [
                    "logs:CreateLogDelivery",
                    "logs:GetLogDelivery",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:ListLogDeliveries",
                    "logs:PutResourcePolicy",
                    "logs:DescribeResourcePolicies",
                    "logs:DescribeLogGroups",
                  ],
                  Resource: "*",
                },
                {
                  Effect: "Allow",
                  Action: [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                  ],
                  Resource: `arn:aws:logs:${region}:${accountId}:log-group:/aws/vendedlogs/states/*`,
                },
              ],
            },
          },
        ],
        tags: [
          { key: "Environment", value: env },
          { key: "Project", value: "ELS-Pipeline" },
        ],
      },
    );

    // ========================================================================
    // Step Functions State Machine
    // ========================================================================

    const aslDefinition = {
      Comment:
        "ELS Normalization Pipeline - Core Stages (without embeddings/recommendations)",
      StartAt: "Ingestion",
      States: {
        Ingestion: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-ingester-${env}`,
            Payload: {
              "run_id.$": "$.run_id",
              "file_path.$": "$.file_path",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              "source_url.$": "$.source_url",
              "publishing_agency.$": "$.publishing_agency",
              "filename.$": "$.filename",
              "document_title.$": "$.document_title",
            },
          },
          ResultPath: "$.ingestion_result",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 2,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "CheckIngestionStatus",
        },
        CheckIngestionStatus: {
          Type: "Choice",
          Choices: [
            {
              Variable: "$.ingestion_result.Payload.status",
              StringEquals: "error",
              Next: "FormatIngestionError",
            },
          ],
          Default: "TextExtraction",
        },
        FormatIngestionError: {
          Type: "Pass",
          Parameters: {
            "run_id.$": "$.run_id",
            "country.$": "$.country",
            "state.$": "$.state",
            "version_year.$": "$.version_year",
            error_info: {
              stage: "ingestion",
              "error.$": "$.ingestion_result.Payload.error",
              "error_type.$": "$.ingestion_result.Payload.error_type",
            },
          },
          Next: "NotifyFailure",
        },
        TextExtraction: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-text-extractor-${env}`,
            Payload: {
              "run_id.$": "$.run_id",
              "output_artifact.$": "$.ingestion_result.Payload.output_artifact",
              "s3_version_id.$": "$.ingestion_result.Payload.s3_version_id",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
            },
          },
          ResultPath: "$.extraction_result",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 5,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "CheckExtractionStatus",
        },
        CheckExtractionStatus: {
          Type: "Choice",
          Choices: [
            {
              Variable: "$.extraction_result.Payload.status",
              StringEquals: "error",
              Next: "FormatExtractionError",
            },
          ],
          Default: "PrepareDetectionBatches",
        },
        FormatExtractionError: {
          Type: "Pass",
          Parameters: {
            "run_id.$": "$.run_id",
            "country.$": "$.country",
            "state.$": "$.state",
            "version_year.$": "$.version_year",
            error_info: {
              stage: "extraction",
              "error.$": "$.extraction_result.Payload.error",
              "error_type.$": "$.extraction_result.Payload.error_type",
            },
          },
          Next: "NotifyFailure",
        },
        PrepareDetectionBatches: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-prepare-detection-batches-${env}`,
            Payload: {
              "run_id.$": "$.run_id",
              "output_artifact.$":
                "$.extraction_result.Payload.output_artifact",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
            },
          },
          ResultPath: "$.detection_batch_prep",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 5,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "DetectBatchMap",
        },
        DetectBatchMap: {
          Type: "Map",
          ItemsPath: "$.detection_batch_prep.Payload.batch_keys",
          MaxConcurrency: 3,
          Iterator: {
            StartAt: "DetectSingleBatch",
            States: {
              DetectSingleBatch: {
                Type: "Task",
                Resource: "arn:aws:states:::lambda:invoke",
                Parameters: {
                  FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-detect-batch-${env}`,
                  "Payload.$": "$",
                },
                End: true,
              },
            },
          },
          ResultPath: "$.detection_batch_results",
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.detection_batch_errors",
              Next: "MergeDetectionResults",
            },
          ],
          Next: "MergeDetectionResults",
        },
        MergeDetectionResults: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-merge-detection-results-${env}`,
            Payload: {
              "manifest_key.$": "$.detection_batch_prep.Payload.manifest_key",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              "run_id.$": "$.run_id",
            },
          },
          ResultPath: "$.detection_result",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 5,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "CheckDetectionStatus",
        },
        CheckDetectionStatus: {
          Type: "Choice",
          Choices: [
            {
              Variable: "$.detection_result.Payload.status",
              StringEquals: "error",
              Next: "FormatDetectionError",
            },
          ],
          Default: "PrepareParseBatches",
        },
        FormatDetectionError: {
          Type: "Pass",
          Parameters: {
            "run_id.$": "$.run_id",
            "country.$": "$.country",
            "state.$": "$.state",
            "version_year.$": "$.version_year",
            error_info: {
              stage: "detection",
              "error.$": "$.detection_result.Payload.error",
            },
          },
          Next: "NotifyFailure",
        },
        PrepareParseBatches: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-prepare-parse-batches-${env}`,
            Payload: {
              "run_id.$": "$.run_id",
              "output_artifact.$": "$.detection_result.Payload.output_artifact",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              "age_band.$": "$.age_band",
            },
          },
          ResultPath: "$.parse_batch_prep",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 5,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "ParseBatchMap",
        },
        ParseBatchMap: {
          Type: "Map",
          ItemsPath: "$.parse_batch_prep.Payload.batch_keys",
          MaxConcurrency: 3,
          Iterator: {
            StartAt: "ParseSingleBatch",
            States: {
              ParseSingleBatch: {
                Type: "Task",
                Resource: "arn:aws:states:::lambda:invoke",
                Parameters: {
                  FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-parse-batch-${env}`,
                  "Payload.$": "$",
                },
                End: true,
              },
            },
          },
          ResultPath: "$.parse_batch_results",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed", "States.Timeout"],
              IntervalSeconds: 10,
              MaxAttempts: 1,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "MergeParseResults",
        },
        MergeParseResults: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-merge-parse-results-${env}`,
            Payload: {
              "manifest_key.$": "$.parse_batch_prep.Payload.manifest_key",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              "run_id.$": "$.run_id",
            },
          },
          ResultPath: "$.parsing_result",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 5,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "CheckParsingStatus",
        },
        CheckParsingStatus: {
          Type: "Choice",
          Choices: [
            {
              Variable: "$.parsing_result.Payload.status",
              StringEquals: "error",
              Next: "FormatParsingError",
            },
          ],
          Default: "Validation",
        },
        FormatParsingError: {
          Type: "Pass",
          Parameters: {
            "run_id.$": "$.run_id",
            "country.$": "$.country",
            "state.$": "$.state",
            "version_year.$": "$.version_year",
            error_info: {
              stage: "parsing",
              "error.$": "$.parsing_result.Payload.error",
            },
          },
          Next: "NotifyFailure",
        },
        Validation: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-validator-${env}`,
            Payload: {
              "run_id.$": "$.run_id",
              "output_artifact.$": "$.parsing_result.Payload.output_artifact",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              "age_band.$": "$.age_band",
              "source_url.$": "$.source_url",
              "publishing_agency.$": "$.publishing_agency",
              "document_title.$": "$.document_title",
              "s3_key.$": "$.ingestion_result.Payload.output_artifact",
            },
          },
          ResultPath: "$.validation_result",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 2,
              MaxAttempts: 2,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "CheckValidationStatus",
        },
        CheckValidationStatus: {
          Type: "Choice",
          Choices: [
            {
              Variable: "$.validation_result.Payload.status",
              StringEquals: "error",
              Next: "FormatValidationError",
            },
          ],
          Default: "DataPersistence",
        },
        FormatValidationError: {
          Type: "Pass",
          Parameters: {
            "run_id.$": "$.run_id",
            "country.$": "$.country",
            "state.$": "$.state",
            "version_year.$": "$.version_year",
            error_info: {
              stage: "validation",
              "error.$": "$.validation_result.Payload.error",
              "error_type.$": "$.validation_result.Payload.error_type",
            },
          },
          Next: "NotifyFailure",
        },
        DataPersistence: {
          Type: "Task",
          Resource: "arn:aws:states:::lambda:invoke",
          Parameters: {
            FunctionName: `arn:aws:lambda:${region}:${accountId}:function:els-persistence-${env}`,
            Payload: {
              "run_id.$": "$.run_id",
              "output_artifact.$":
                "$.validation_result.Payload.output_artifact",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
            },
          },
          ResultPath: "$.persistence_result",
          Retry: [
            {
              ErrorEquals: ["States.TaskFailed"],
              IntervalSeconds: 2,
              MaxAttempts: 3,
              BackoffRate: 2.0,
            },
          ],
          Catch: [
            {
              ErrorEquals: ["States.ALL"],
              ResultPath: "$.error_info",
              Next: "NotifyFailure",
            },
          ],
          Next: "CheckPersistenceStatus",
        },
        CheckPersistenceStatus: {
          Type: "Choice",
          Choices: [
            {
              Variable: "$.persistence_result.Payload.status",
              StringEquals: "error",
              Next: "FormatPersistenceError",
            },
          ],
          Default: "NotifySuccess",
        },
        FormatPersistenceError: {
          Type: "Pass",
          Parameters: {
            "run_id.$": "$.run_id",
            "country.$": "$.country",
            "state.$": "$.state",
            "version_year.$": "$.version_year",
            error_info: {
              stage: "persistence",
              "error.$": "$.persistence_result.Payload.error",
              "error_type.$": "$.persistence_result.Payload.error_type",
            },
          },
          Next: "NotifyFailure",
        },
        NotifySuccess: {
          Type: "Task",
          Resource: "arn:aws:states:::sns:publish",
          Parameters: {
            TopicArn: notificationTopic.topicArn,
            Subject: "ELS Pipeline Completed Successfully",
            Message: {
              "run_id.$": "$.run_id",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              status: "completed",
              "total_indicators.$": "$.parsing_result.Payload.total_indicators",
              "total_validated.$":
                "$.validation_result.Payload.total_validated",
              "records_persisted.$":
                "$.persistence_result.Payload.records_persisted",
            },
          },
          End: true,
        },
        NotifyFailure: {
          Type: "Task",
          Resource: "arn:aws:states:::sns:publish",
          Parameters: {
            TopicArn: notificationTopic.topicArn,
            Subject: "ELS Pipeline Failed",
            Message: {
              "run_id.$": "$.run_id",
              "country.$": "$.country",
              "state.$": "$.state",
              "version_year.$": "$.version_year",
              status: "failed",
              "error_info.$": "$.error_info",
            },
          },
          Next: "FailState",
        },
        FailState: {
          Type: "Fail",
          Error: "PipelineExecutionFailed",
          Cause: "One or more pipeline stages failed",
        },
      },
    };

    const stateMachine = new sfn.CfnStateMachine(this, "PipelineStateMachine", {
      stateMachineName: `els-core-pipeline-${env}`,
      roleArn: stepFunctionsExecutionRole.attrArn,
      loggingConfiguration: {
        level: "ALL",
        includeExecutionData: true,
        destinations: [
          {
            cloudWatchLogsLogGroup: {
              logGroupArn: pipelineLogGroup.logGroupArn,
            },
          },
        ],
      },
      definitionString: cdk.Lazy.string({
        produce: () => JSON.stringify(aslDefinition),
      }),
      tags: [
        { key: "Environment", value: env },
        { key: "Project", value: "ELS-Pipeline" },
      ],
    });

    // ========================================================================
    // Placeholder Parameter (matches original CFN template)
    // ========================================================================

    new ssm.CfnParameter(this, "PlaceholderParameter", {
      name: `/els-pipeline/${env}/placeholder`,
      type: "String",
      value: "Infrastructure template initialized",
      description: "Placeholder parameter for ELS pipeline",
    });

    // ========================================================================
    // Cross-Stack Exports (CfnOutput)
    // ========================================================================

    new cdk.CfnOutput(this, "EnvironmentName", {
      description: "Environment name",
      value: env,
      exportName: `${this.stackName}-EnvironmentName`,
    });

    new cdk.CfnOutput(this, "Region", {
      description: "AWS Region",
      value: region,
      exportName: `${this.stackName}-Region`,
    });

    new cdk.CfnOutput(this, "RawDocumentsBucketName", {
      description: "S3 bucket for raw documents",
      value: this.rawDocumentsBucket.bucketName,
      exportName: `${this.stackName}-RawDocumentsBucket`,
    });

    new cdk.CfnOutput(this, "RawDocumentsBucketArn", {
      description: "ARN of the raw documents bucket",
      value: this.rawDocumentsBucket.bucketArn,
      exportName: `${this.stackName}-RawDocumentsBucketArn`,
    });

    new cdk.CfnOutput(this, "IngesterLambdaRoleArn", {
      description: "ARN of the Ingester Lambda IAM role",
      value: ingesterLambdaRole.attrArn,
      exportName: `${this.stackName}-IngesterLambdaRoleArn`,
    });

    new cdk.CfnOutput(this, "TextExtractorLambdaRoleArn", {
      description: "ARN of the Text Extractor Lambda IAM role",
      value: textExtractorLambdaRole.attrArn,
      exportName: `${this.stackName}-TextExtractorLambdaRoleArn`,
    });

    new cdk.CfnOutput(this, "StructureDetectorLambdaRoleArn", {
      description: "ARN of the Structure Detector Lambda IAM role",
      value: structureDetectorLambdaRole.attrArn,
      exportName: `${this.stackName}-StructureDetectorLambdaRoleArn`,
    });

    new cdk.CfnOutput(this, "HierarchyParserLambdaRoleArn", {
      description: "ARN of the Hierarchy Parser Lambda IAM role",
      value: hierarchyParserLambdaRole.attrArn,
      exportName: `${this.stackName}-HierarchyParserLambdaRoleArn`,
    });

    new cdk.CfnOutput(this, "ProcessedJsonBucketName", {
      description: "S3 bucket for processed JSON records",
      value: this.processedJsonBucket.bucketName,
      exportName: `${this.stackName}-ProcessedJsonBucket`,
    });

    new cdk.CfnOutput(this, "ProcessedJsonBucketArn", {
      description: "ARN of the processed JSON bucket",
      value: this.processedJsonBucket.bucketArn,
      exportName: `${this.stackName}-ProcessedJsonBucketArn`,
    });

    new cdk.CfnOutput(this, "ValidatorLambdaRoleArn", {
      description: "ARN of the Validator Lambda IAM role",
      value: validatorLambdaRole.attrArn,
      exportName: `${this.stackName}-ValidatorLambdaRoleArn`,
    });

    new cdk.CfnOutput(this, "DatabaseClusterEndpoint", {
      description: "Aurora PostgreSQL cluster endpoint",
      value: this.databaseCluster.attrEndpointAddress,
      exportName: `${this.stackName}-DatabaseClusterEndpoint`,
    });

    new cdk.CfnOutput(this, "DatabaseClusterArn", {
      description: "ARN of the Aurora PostgreSQL cluster",
      value: this.databaseCluster.attrDbClusterArn,
      exportName: `${this.stackName}-DatabaseClusterArn`,
    });

    new cdk.CfnOutput(this, "DatabaseSecretArn", {
      description: "ARN of the database credentials secret",
      value: this.databaseSecret.ref,
      exportName: `${this.stackName}-DatabaseSecretArn`,
    });

    new cdk.CfnOutput(this, "DatabaseVPCId", {
      description: "VPC ID for the database",
      value: this.vpc.ref,
      exportName: `${this.stackName}-DatabaseVPCId`,
    });

    new cdk.CfnOutput(this, "LambdaSecurityGroupId", {
      description: "Security group ID for Lambda functions",
      value: this.lambdaSecurityGroup.ref,
      exportName: `${this.stackName}-LambdaSecurityGroupId`,
    });

    new cdk.CfnOutput(this, "DatabaseSubnet1Id", {
      description: "Database subnet 1 ID",
      value: this.databaseSubnet1.ref,
      exportName: `${this.stackName}-DatabaseSubnet1Id`,
    });

    new cdk.CfnOutput(this, "DatabaseSubnet2Id", {
      description: "Database subnet 2 ID",
      value: this.databaseSubnet2.ref,
      exportName: `${this.stackName}-DatabaseSubnet2Id`,
    });

    new cdk.CfnOutput(this, "PipelineStateMachineArn", {
      description: "ARN of the Step Functions state machine for core pipeline",
      value: stateMachine.ref,
      exportName: `${this.stackName}-PipelineStateMachineArn`,
    });

    new cdk.CfnOutput(this, "PipelineNotificationTopicArn", {
      description: "ARN of the SNS topic for pipeline notifications",
      value: notificationTopic.topicArn,
      exportName: `${this.stackName}-PipelineNotificationTopicArn`,
    });

    new cdk.CfnOutput(this, "StepFunctionsExecutionRoleArn", {
      description: "ARN of the Step Functions execution role",
      value: stepFunctionsExecutionRole.attrArn,
      exportName: `${this.stackName}-StepFunctionsExecutionRoleArn`,
    });

    new cdk.CfnOutput(this, "PipelineLogGroupName", {
      description: "CloudWatch Log Group for Step Functions",
      value: pipelineLogGroup.logGroupName,
      exportName: `${this.stackName}-PipelineLogGroupName`,
    });

    // Lambda Function ARN exports
    new cdk.CfnOutput(this, "IngesterLambdaFunctionArn", {
      description: "ARN of the Ingester Lambda function",
      value: ingesterLambda.function.functionArn,
      exportName: `${this.stackName}-IngesterLambdaFunctionArn`,
    });

    new cdk.CfnOutput(this, "TextExtractorLambdaFunctionArn", {
      description: "ARN of the Text Extractor Lambda function",
      value: textExtractorLambda.function.functionArn,
      exportName: `${this.stackName}-TextExtractorLambdaFunctionArn`,
    });

    new cdk.CfnOutput(this, "StructureDetectorLambdaFunctionArn", {
      description: "ARN of the Structure Detector Lambda function",
      value: structureDetectorLambda.function.functionArn,
      exportName: `${this.stackName}-StructureDetectorLambdaFunctionArn`,
    });

    new cdk.CfnOutput(this, "HierarchyParserLambdaFunctionArn", {
      description: "ARN of the Hierarchy Parser Lambda function",
      value: hierarchyParserLambda.function.functionArn,
      exportName: `${this.stackName}-HierarchyParserLambdaFunctionArn`,
    });

    new cdk.CfnOutput(this, "ValidatorLambdaFunctionArn", {
      description: "ARN of the Validator Lambda function",
      value: validatorLambda.function.functionArn,
      exportName: `${this.stackName}-ValidatorLambdaFunctionArn`,
    });

    new cdk.CfnOutput(this, "PersistenceLambdaFunctionArn", {
      description: "ARN of the Persistence Lambda function",
      value: persistenceLambda.function.functionArn,
      exportName: `${this.stackName}-PersistenceLambdaFunctionArn`,
    });
  }
}
