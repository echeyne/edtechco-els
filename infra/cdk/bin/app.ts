#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { ElsPipelineStack } from "../lib/pipeline-stack";
import { ElsAppStack } from "../lib/app-stack";
import { ElsPlanningStack } from "../lib/planning-stack";
import { LandingSiteStack } from "../lib/landing-site-stack";

const app = new cdk.App();

const env = app.node.tryGetContext("environment") || "dev";
const region = app.node.tryGetContext("region") || "us-east-1";
const targetStack = app.node.tryGetContext("targetStack") as string | undefined;

// Helper: only instantiate a stack if no target is specified, or it matches
const shouldCreate = (stackName: string) =>
  !targetStack || targetStack === stackName;

if (
  shouldCreate(`els-pipeline-${env}`) ||
  shouldCreate(`els-app-${env}`) ||
  shouldCreate(`els-planning-${env}`)
) {
  const pipelineStack = new ElsPipelineStack(app, `els-pipeline-${env}`, {
    environmentName: env,
    env: { region },
  });

  if (shouldCreate(`els-app-${env}`)) {
    const appStack = new ElsAppStack(app, `els-app-${env}`, {
      environmentName: env,
      pipelineStackName: `els-pipeline-${env}`,
      descopeProjectId: process.env.DESCOPE_PROJECT_ID!,
      customDomainName: app.node.tryGetContext("customDomain"),
      hostedZoneId: app.node.tryGetContext("hostedZoneId"),
      env: { region },
    });
    appStack.addDependency(pipelineStack);
  }

  if (shouldCreate(`els-planning-${env}`)) {
    const planningStack = new ElsPlanningStack(app, `els-planning-${env}`, {
      environmentName: env,
      pipelineStackName: `els-pipeline-${env}`,
      descopeProjectId: process.env.DESCOPE_PROJECT_ID!,
      customDomainName: app.node.tryGetContext("planningDomain"),
      hostedZoneId: app.node.tryGetContext("hostedZoneId"),
      env: { region },
    });
    planningStack.addDependency(pipelineStack);
  }
}

if (shouldCreate(`els-landing-${env}`)) {
  new LandingSiteStack(app, `els-landing-${env}`, {
    environmentName: env,
    customDomainName: app.node.tryGetContext("landingDomain"),
    hostedZoneId: app.node.tryGetContext("hostedZoneId"),
    env: { region },
  });
}
