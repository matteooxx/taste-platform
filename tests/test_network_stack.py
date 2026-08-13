import aws_cdk as cdk
from aws_cdk import assertions
from stacks.network_stack import NetworkStack


def test_vpc_created():
    app = cdk.App()
    stack = NetworkStack(app, "TestNetwork")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::VPC", 1)


def test_no_nat_gateway():
    app = cdk.App()
    stack = NetworkStack(app, "TestNetwork")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::NatGateway", 0)


def test_vpc_endpoints_created():
    app = cdk.App()
    stack = NetworkStack(app, "TestNetwork")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::VPCEndpoint", 8)
