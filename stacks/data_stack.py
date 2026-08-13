from aws_cdk import (
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_kms as kms,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class DataStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, kms_key: kms.IKey, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.table = dynamodb.Table(
            self, "TasteProfileTable",
            table_name="taste-profile",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="item_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=kms_key,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True,
            ),
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.nas_credentials_secret = secretsmanager.Secret(
            self, "NasCredentials",
            secret_name="taste-platform/nas-credentials",
            description="IAM access key for NAS container",
            encryption_key=kms_key,
        )

        self.cognito_client_secret = secretsmanager.Secret(
            self, "CognitoClientSecret",
            secret_name="taste-platform/cognito-client-secret",
            description="Cognito app client secret",
            encryption_key=kms_key,
        )
