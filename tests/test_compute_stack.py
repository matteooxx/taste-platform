import aws_cdk as cdk
from aws_cdk import assertions
from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack


def _create_compute_stack():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    security = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    data = DataStack(app, "TestData", kms_key=security.kms_key)
    stack = ComputeStack(
        app, "TestCompute",
        kms_key=security.kms_key,
        table=data.table,
        cognito_user_pool=security.user_pool,
    )
    return stack


def test_five_lambda_functions():
    stack = _create_compute_stack()
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::Lambda::Function", 5)


def test_lambda_runtime_python312():
    stack = _create_compute_stack()
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::Lambda::Function", {
        "Runtime": "python3.12",
    })


def test_xray_tracing_enabled():
    stack = _create_compute_stack()
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::Lambda::Function", {
        "TracingConfig": {"Mode": "Active"},
    })


def test_eventbridge_rule_created():
    stack = _create_compute_stack()
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::Events::Rule", 1)


def test_sns_topic_created():
    stack = _create_compute_stack()
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::SNS::Topic", 1)
