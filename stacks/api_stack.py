from aws_cdk import (
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_cognito as cognito,
    aws_lambda as _lambda,
    aws_sns as sns,
    CfnOutput,
)
from constructs import Construct


class ApiStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str,
        chat_handler: _lambda.IFunction,
        history_handler: _lambda.IFunction,
        user_pool: cognito.IUserPool,
        user_pool_client: cognito.IUserPoolClient,
        sns_topic: sns.ITopic,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
        )

        http_api = apigwv2.HttpApi(
            self, "HttpApi",
            api_name="taste-platform-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.GET],
                allow_headers=["Authorization", "Content-Type"],
            ),
            default_authorizer=jwt_authorizer,
        )

        http_api.add_routes(
            path="/health",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "HealthIntegration", handler=chat_handler,
            ),
            authorizer=apigwv2.HttpNoneAuthorizer(),
        )

        http_api.add_routes(
            path="/history",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "HistoryIntegration", handler=history_handler,
            ),
        )

        http_api.add_routes(
            path="/chat",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "ChatIntegration", handler=chat_handler,
            ),
        )

        default_stage = http_api.default_stage
        cfn_stage = default_stage.node.default_child
        cfn_stage.add_property_override("DefaultRouteSettings", {
            "ThrottlingBurstLimit": 50,
            "ThrottlingRateLimit": 100,
        })

        CfnOutput(self, "ApiUrl", value=http_api.url or "")
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
