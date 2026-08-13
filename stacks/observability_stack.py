from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_sns as sns,
    aws_cloudtrail as cloudtrail,
    aws_s3 as s3,
    aws_config as config,
)
from constructs import Construct


class ObservabilityStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str,
        kms_key: kms.IKey,
        lambda_functions: dict[str, _lambda.IFunction],
        sns_topic: sns.ITopic,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        for name, fn in lambda_functions.items():
            log_group = logs.LogGroup(
                self, f"{name}LogGroup",
                log_group_name=f"/aws/lambda/taste-platform-{name.replace('_', '-')}",
                retention=logs.RetentionDays.ONE_MONTH,
                encryption_key=kms_key,
                removal_policy=RemovalPolicy.DESTROY,
            )

            error_alarm = cloudwatch.Alarm(
                self, f"{name}ErrorAlarm",
                alarm_name=f"taste-platform-{name}-errors",
                metric=fn.metric_errors(period=Duration.minutes(5)),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            error_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        trail_bucket = s3.Bucket(
            self, "TrailBucket",
            bucket_name=f"taste-platform-cloudtrail-{self.account}",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(90)),
            ],
            removal_policy=RemovalPolicy.RETAIN,
        )

        cloudtrail.Trail(
            self, "Trail",
            trail_name="taste-platform-trail",
            bucket=trail_bucket,
            encryption_key=kms_key,
            enable_file_validation=True,
            is_multi_region_trail=False,
            include_global_service_events=True,
        )

        config.ManagedRule(
            self, "DynamoDbEncryption",
            identifier="DYNAMODB_TABLE_ENCRYPTED_KMS",
            rule_scope=config.RuleScope.from_resources([
                config.ResourceType.DYNAMODB_TABLE,
            ]),
        )

        config.ManagedRule(
            self, "LambdaInsideVpc",
            identifier="LAMBDA_INSIDE_VPC",
        )

        config.ManagedRule(
            self, "S3BucketPublicReadProhibited",
            identifier="S3_BUCKET_PUBLIC_READ_PROHIBITED",
        )

        config.ManagedRule(
            self, "CloudTrailEnabled",
            identifier="CLOUD_TRAIL_ENABLED",
        )

        config.ManagedRule(
            self, "KmsKeyRotationEnabled",
            identifier="CMK_BACKING_KEY_ROTATION_ENABLED",
        )
