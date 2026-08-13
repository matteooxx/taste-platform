#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack
from stacks.observability_stack import ObservabilityStack
from stacks.api_stack import ApiStack
from stacks.agent_stack import AgentStack
from stacks.streaming_stack import StreamingStack

app = cdk.App()

account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = (
    app.node.try_get_context("region")
    or os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or "eu-west-1"
)
prefix = app.node.try_get_context("project_prefix") or "taste-platform"

env = cdk.Environment(account=account, region=region)

tags = {
    "Project": prefix,
    "Environment": "production",
    "Owner": os.environ.get("TASTE_PLATFORM_OWNER", "project-owner"),
    "DataClassification": "private",
}

network_stack = NetworkStack(app, f"{prefix}-network", env=env)
security_stack = SecurityStack(app, f"{prefix}-security", env=env, vpc=network_stack.vpc)
data_stack = DataStack(
    app, f"{prefix}-data", env=env,
    kms_key=security_stack.kms_key,
)
compute_stack = ComputeStack(
    app, f"{prefix}-compute", env=env,
    kms_key=security_stack.kms_key,
    table=data_stack.table,
    cognito_user_pool=security_stack.user_pool,
)
observability_stack = ObservabilityStack(
    app, f"{prefix}-observability", env=env,
    kms_key=security_stack.kms_key,
    lambda_functions=compute_stack.lambda_functions,
    sns_topic=compute_stack.alert_topic,
)
api_stack = ApiStack(
    app, f"{prefix}-api", env=env,
    chat_handler=compute_stack.lambda_functions["chat_handler"],
    history_handler=compute_stack.lambda_functions["history"],
    user_pool=security_stack.user_pool,
    user_pool_client=security_stack.user_pool_client,
    sns_topic=compute_stack.alert_topic,
)
agent_stack = AgentStack(
    app, f"{prefix}-agent", env=env,
    update_profile_fn=compute_stack.update_profile,
    get_recommendations_fn=compute_stack.get_recommendations,
    chat_handler_fn=compute_stack.chat_handler,
)
streaming_stack = StreamingStack(
    app, f"{prefix}-streaming", env=env,
    kms_key=security_stack.kms_key,
)

for stack in [network_stack, security_stack, data_stack, compute_stack, observability_stack, api_stack, agent_stack, streaming_stack]:
    for key, value in tags.items():
        cdk.Tags.of(stack).add(key, value)

app.synth()
