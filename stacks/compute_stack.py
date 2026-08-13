from aws_cdk import (
    CfnParameter,
    Duration,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_cognito as cognito,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct
import os


class ComputeStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str,
        kms_key: kms.IKey,
        table: dynamodb.ITable,
        cognito_user_pool: cognito.IUserPool,
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

        self.alert_topic = sns.Topic(
            self, "AlertTopic",
            topic_name="taste-platform-alerts",
            master_key=kms_key,
        )

        digest_dlq = sqs.Queue(
            self, "WeeklyDigestDLQ",
            queue_name="taste-platform-weekly-digest-dlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=kms_key,
        )

        cloudwatch.Alarm(
            self, "DLQAlarm",
            alarm_name="taste-platform-dlq-messages",
            metric=digest_dlq.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        ).add_alarm_action(cw_actions.SnsAction(self.alert_topic))

        layer = _lambda.LayerVersion(
            self, "SharedLayer",
            layer_version_name="taste-platform-shared",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "layer")
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared utilities for Taste Platform Lambda functions",
        )

        common_env = {
            "TABLE_NAME": table.table_name,
            "KMS_KEY_ID": kms_key.key_id,
            "POWERTOOLS_SERVICE_NAME": "taste-platform",
        }

        common_lambda_props = {
            "runtime": _lambda.Runtime.PYTHON_3_12,
            "layers": [layer],
            "tracing": _lambda.Tracing.ACTIVE,
            "timeout": Duration.seconds(30),
            "memory_size": 256,
        }

        agent_arn = f"arn:aws:bedrock:{self.region}:{self.account}:agent/{agent_id}"
        agent_alias_arn = (
            f"arn:aws:bedrock:{self.region}:{self.account}:"
            f"agent-alias/{agent_id}/*"
        )

        # --- chat_handler (kept for /health endpoint and legacy /chat) ---
        chat_handler_role = iam.Role(
            self, "ChatHandlerRole",
            role_name="taste-platform-chat-handler-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        chat_handler_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeAgent"],
            resources=[agent_arn, agent_alias_arn],
        ))
        chat_handler_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem"],
            resources=[table.table_arn],
        ))
        chat_handler_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=[kms_key.key_arn],
        ))

        self.chat_handler = _lambda.Function(
            self, "ChatHandler",
            function_name="taste-platform-chat-handler",
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "chat_handler")
            ),
            role=chat_handler_role,
            environment={
                **common_env,
                "BEDROCK_AGENT_ID": agent_id,
                "BEDROCK_AGENT_ALIAS_ID": agent_alias_id,
            },
            reserved_concurrent_executions=10,
            **common_lambda_props,
        )

        # --- update_profile ---
        update_profile_role = iam.Role(
            self, "UpdateProfileRole",
            role_name="taste-platform-update-profile-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        update_profile_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[table.table_arn],
        ))
        update_profile_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt", "kms:GenerateDataKey"],
            resources=[kms_key.key_arn],
        ))

        self.update_profile = _lambda.Function(
            self, "UpdateProfile",
            function_name="taste-platform-update-profile",
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "update_profile")
            ),
            role=update_profile_role,
            environment=common_env,
            **common_lambda_props,
        )

        # --- get_recommendations ---
        get_recommendations_role = iam.Role(
            self, "GetRecommendationsRole",
            role_name="taste-platform-get-recommendations-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        get_recommendations_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:Query"],
            resources=[table.table_arn],
        ))
        get_recommendations_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=[kms_key.key_arn],
        ))

        self.get_recommendations = _lambda.Function(
            self, "GetRecommendations",
            function_name="taste-platform-get-recommendations",
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "get_recommendations")
            ),
            role=get_recommendations_role,
            environment=common_env,
            **common_lambda_props,
        )

        # --- history (new: direct DynamoDB query for frontend) ---
        history_role = iam.Role(
            self, "HistoryRole",
            role_name="taste-platform-history-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        history_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:Query"],
            resources=[table.table_arn],
        ))
        history_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=[kms_key.key_arn],
        ))

        self.history = _lambda.Function(
            self, "History",
            function_name="taste-platform-history",
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "history")
            ),
            role=history_role,
            environment=common_env,
            **common_lambda_props,
        )

        # --- weekly_digest (uses Haiku 4.5 — cheaper/faster for summaries) ---
        weekly_digest_role = iam.Role(
            self, "WeeklyDigestRole",
            role_name="taste-platform-weekly-digest-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        weekly_digest_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:Scan"],
            resources=[table.table_arn],
        ))
        weekly_digest_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
            ],
        ))
        weekly_digest_role.add_to_policy(iam.PolicyStatement(
            actions=["sns:Publish"],
            resources=[self.alert_topic.topic_arn],
        ))
        weekly_digest_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt", "kms:GenerateDataKey"],
            resources=[kms_key.key_arn],
        ))
        weekly_digest_role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage"],
            resources=[digest_dlq.queue_arn],
        ))

        self.weekly_digest = _lambda.Function(
            self, "WeeklyDigest",
            function_name="taste-platform-weekly-digest",
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "lambda", "weekly_digest")
            ),
            role=weekly_digest_role,
            environment={
                **common_env,
                "SNS_TOPIC_ARN": self.alert_topic.topic_arn,
                "BEDROCK_MODEL_ID": "anthropic.claude-haiku-4-5-20251001-v1:0",
            },
            timeout=Duration.minutes(5),
            dead_letter_queue=digest_dlq,
            reserved_concurrent_executions=2,
            **{k: v for k, v in common_lambda_props.items() if k not in ("timeout",)},
        )

        events.Rule(
            self, "WeeklyDigestSchedule",
            rule_name="taste-platform-weekly-digest-schedule",
            schedule=events.Schedule.cron(
                minute="0", hour="8", week_day="MON",
            ),
            targets=[targets.LambdaFunction(self.weekly_digest)],
        )

        self.lambda_functions = {
            "chat_handler": self.chat_handler,
            "update_profile": self.update_profile,
            "get_recommendations": self.get_recommendations,
            "history": self.history,
            "weekly_digest": self.weekly_digest,
        }
