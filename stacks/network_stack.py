from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct


class NetworkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self, "Vpc",
            vpc_name="taste-platform-vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="private-isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        sg_endpoints = ec2.SecurityGroup(
            self, "VpcEndpointSg",
            vpc=self.vpc,
            description="Security group for VPC interface endpoints",
            allow_all_outbound=False,
        )
        sg_endpoints.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(443),
            "Allow HTTPS from VPC",
        )

        interface_services = [
            ("Bedrock", ec2.InterfaceVpcEndpointAwsService("bedrock-runtime")),
            ("BedrockAgent", ec2.InterfaceVpcEndpointAwsService("bedrock-agent-runtime")),
            ("SecretsManager", ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER),
            ("CloudWatch", ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS),
            ("Sts", ec2.InterfaceVpcEndpointAwsService("sts")),
            ("Sns", ec2.InterfaceVpcEndpointAwsService("sns")),
        ]

        for name, service in interface_services:
            self.vpc.add_interface_endpoint(
                f"{name}Endpoint",
                service=service,
                security_groups=[sg_endpoints],
                private_dns_enabled=True,
            )
