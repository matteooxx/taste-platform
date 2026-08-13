import aws_cdk as cdk
from aws_cdk import assertions
from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.data_stack import DataStack


def test_dynamodb_table_created():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    security = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    stack = DataStack(app, "TestData", kms_key=security.kms_key)
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "taste-profile",
        "KeySchema": [
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "item_id", "KeyType": "RANGE"},
        ],
        "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
        "TimeToLiveSpecification": {
            "AttributeName": "expires_at",
            "Enabled": True,
        },
    })


def test_secrets_created():
    app = cdk.App()
    network = NetworkStack(app, "TestNetwork")
    security = SecurityStack(app, "TestSecurity", vpc=network.vpc)
    stack = DataStack(app, "TestData", kms_key=security.kms_key)
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::SecretsManager::Secret", 2)
