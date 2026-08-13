import aws_cdk as cdk
from aws_cdk import assertions
from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack


def test_kms_key_rotation_enabled():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    stack = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties("AWS::KMS::Key", {
        "EnableKeyRotation": True,
    })


def test_cognito_user_pool_created():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    stack = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Cognito::UserPool", 1)


def test_waf_acl_created():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    stack = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::WAFv2::WebACL", 1)
