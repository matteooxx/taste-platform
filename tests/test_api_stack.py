import aws_cdk as cdk
from aws_cdk import assertions
from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack
from stacks.api_stack import ApiStack


def _create_api_stack():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    security = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    data = DataStack(app, "TestData", kms_key=security.kms_key)
    compute = ComputeStack(
        app, "TestCompute",
        kms_key=security.kms_key,
        table=data.table,
        cognito_user_pool=security.user_pool,
    )
    stack = ApiStack(
        app, "TestApi",
        chat_handler=compute.chat_handler,
        history_handler=compute.history,
        user_pool=security.user_pool,
        user_pool_client=security.user_pool_client,
        sns_topic=compute.alert_topic,
    )
    return stack


def test_http_api_created():
    stack = _create_api_stack()
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::ApiGatewayV2::Api", 1)


def test_routes_created():
    stack = _create_api_stack()
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::ApiGatewayV2::Route", 3)
