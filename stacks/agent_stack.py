from aws_cdk import (
    Stack,
    CfnOutput,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_lambda as _lambda,
)
from constructs import Construct


AGENT_INSTRUCTION = (
    "You are a personal taste advisor for the current user. You have access to "
    "their complete history of movies, TV shows, anime, games and music they "
    "have watched, played or listened to, along with their ratings and "
    "preferences. "
    "Your goal is to provide highly personalized recommendations based on "
    "their taste profile, explain why something will or will not suit them "
    "based on past preferences, and proactively surface new releases that "
    "match their taste. Always be concise and direct. When the user tells you "
    "about something they watched, played or listened to, always update "
    "their profile. Never mention that you are an AI or that you are "
    "analyzing data."
)

FUNCTION_SCHEMA_UPDATE = {
    "name": "update_profile",
    "description": "Updates the user's taste profile with a new item they watched, played, or listened to.",
    "parameters": {
        "user_id": {
            "type": "string",
            "description": "The user's unique identifier",
            "required": True,
        },
        "item_type": {
            "type": "string",
            "description": "Type of media: movie, show, anime, game, or music",
            "required": True,
        },
        "item_name": {
            "type": "string",
            "description": "Name of the movie, show, game, or music",
            "required": True,
        },
        "rating": {
            "type": "integer",
            "description": "Rating from 1 to 5",
            "required": True,
        },
        "notes": {
            "type": "string",
            "description": "Optional notes about why they liked or disliked it",
            "required": False,
        },
    },
}

FUNCTION_SCHEMA_RECOMMENDATIONS = {
    "name": "get_recommendations",
    "description": "Retrieves the user's taste profile to provide context for recommendations.",
    "parameters": {
        "user_id": {
            "type": "string",
            "description": "The user's unique identifier",
            "required": True,
        },
        "item_type": {
            "type": "string",
            "description": "Optional filter by media type: movie, show, anime, game, or music",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of profile items to return (default 20)",
            "required": False,
        },
    },
}


class AgentStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str,
        update_profile_fn: _lambda.IFunction,
        get_recommendations_fn: _lambda.IFunction,
        chat_handler_fn: _lambda.IFunction,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        agent_role = iam.Role(
            self, "AgentRole",
            role_name="taste-platform-bedrock-agent-role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
        )
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/eu.anthropic.claude-sonnet-4-6",
            ],
        ))

        agent_arn = f"arn:aws:bedrock:{self.region}:{self.account}:agent/*"

        update_profile_fn.add_permission(
            "BedrockAgentInvoke",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            source_arn=agent_arn,
        )
        get_recommendations_fn.add_permission(
            "BedrockAgentInvoke",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            source_arn=agent_arn,
        )

        cfn_agent = bedrock.CfnAgent(
            self, "Agent",
            agent_name="taste-platform-agent",
            agent_resource_role_arn=agent_role.role_arn,
            foundation_model="eu.anthropic.claude-sonnet-4-6",
            instruction=AGENT_INSTRUCTION,
            idle_session_ttl_in_seconds=1800,
            auto_prepare=True,
            action_groups=[
                bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="taste-platform-actions",
                    action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                        lambda_=update_profile_fn.function_arn,
                    ),
                    function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                        functions=[
                            bedrock.CfnAgent.FunctionProperty(
                                name=FUNCTION_SCHEMA_UPDATE["name"],
                                description=FUNCTION_SCHEMA_UPDATE["description"],
                                parameters={
                                    k: bedrock.CfnAgent.ParameterDetailProperty(
                                        type=v["type"],
                                        description=v["description"],
                                        required=v["required"],
                                    )
                                    for k, v in FUNCTION_SCHEMA_UPDATE["parameters"].items()
                                },
                            ),
                        ],
                    ),
                ),
                bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="taste-platform-recommendations",
                    action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                        lambda_=get_recommendations_fn.function_arn,
                    ),
                    function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                        functions=[
                            bedrock.CfnAgent.FunctionProperty(
                                name=FUNCTION_SCHEMA_RECOMMENDATIONS["name"],
                                description=FUNCTION_SCHEMA_RECOMMENDATIONS["description"],
                                parameters={
                                    k: bedrock.CfnAgent.ParameterDetailProperty(
                                        type=v["type"],
                                        description=v["description"],
                                        required=v["required"],
                                    )
                                    for k, v in FUNCTION_SCHEMA_RECOMMENDATIONS["parameters"].items()
                                },
                            ),
                        ],
                    ),
                ),
            ],
        )

        cfn_alias = bedrock.CfnAgentAlias(
            self, "AgentAlias",
            agent_id=cfn_agent.attr_agent_id,
            agent_alias_name="production",
            description="Production alias for taste-platform-agent",
        )
        cfn_alias.add_dependency(cfn_agent)

        CfnOutput(self, "AgentId", value=cfn_agent.attr_agent_id)
        CfnOutput(self, "AgentAliasId", value=cfn_alias.attr_agent_alias_id)
        CfnOutput(self, "AgentArn", value=cfn_agent.attr_agent_arn)

        self.agent_id = cfn_agent.attr_agent_id
        self.agent_alias_id = cfn_alias.attr_agent_alias_id
