from aws_cdk import (
    CfnParameter,
    Duration,
    Stack,
    CfnOutput,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as _lambda,
)
from constructs import Construct
import os


class StreamingStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str,
        kms_key: kms.IKey,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        agent_id = CfnParameter(
            self,
            "BedrockAgentId",
            type="String",
            allowed_pattern="[A-Za-z0-9]{10}",
            description="Bedrock Agent ID created for this deployment",
        ).value_as_string
        agent_alias_id = CfnParameter(
            self,
            "BedrockAgentAliasId",
            type="String",
            allowed_pattern="[A-Za-z0-9]{10}",
            description="Bedrock Agent alias ID created for this deployment",
        ).value_as_string
        invoker_role_arn = CfnParameter(
            self,
            "InvokerRoleArn",
            type="String",
            allowed_pattern="arn:[^:]+:iam::[0-9]{12}:role/.+",
            description=(
                "Existing IAM role allowed to invoke the AWS_IAM Function URL"
            ),
        ).value_as_string

        stream_role = iam.Role(
            self, "StreamChatRole",
            role_name="taste-platform-chat-stream-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        stream_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeAgent"],
            resources=[
                f"arn:aws:bedrock:{self.region}:{self.account}:agent/{agent_id}",
                (
                    f"arn:aws:bedrock:{self.region}:{self.account}:"
                    f"agent-alias/{agent_id}/*"
                ),
            ],
        ))
        stream_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=[kms_key.key_arn],
        ))

        self.stream_function = _lambda.Function(
            self, "ChatStream",
            function_name="taste-platform-chat-stream",
            handler="handler.lambda_handler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "chat_stream")
            ),
            role=stream_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            tracing=_lambda.Tracing.ACTIVE,
            reserved_concurrent_executions=5,
            environment={
                "BEDROCK_AGENT_ID": agent_id,
                "BEDROCK_AGENT_ALIAS_ID": agent_alias_id,
                "POWERTOOLS_SERVICE_NAME": "taste-platform",
            },
        )

        fn_url = self.stream_function.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.AWS_IAM,
            invoke_mode=_lambda.InvokeMode.RESPONSE_STREAM,
            cors=_lambda.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[_lambda.HttpMethod.POST],
                allowed_headers=["Content-Type", "X-Amz-Date", "X-Amz-Security-Token", "Authorization"],
                max_age=Duration.hours(1),
            ),
        )

        _lambda.CfnPermission(
            self,
            "InvokerFunctionUrlPermission",
            action="lambda:InvokeFunctionUrl",
            function_name=self.stream_function.function_name,
            function_url_auth_type="AWS_IAM",
            principal=invoker_role_arn,
        )
        _lambda.CfnPermission(
            self,
            "InvokerFunctionPermission",
            action="lambda:InvokeFunction",
            function_name=self.stream_function.function_name,
            invoked_via_function_url=True,
            principal=invoker_role_arn,
        )

        CfnOutput(self, "StreamFunctionUrl", value=fn_url.url)
        CfnOutput(self, "ConfiguredInvokerRoleArn", value=invoker_role_arn)
