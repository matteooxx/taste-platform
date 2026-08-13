from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_cognito as cognito,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_kms as kms,
    aws_wafv2 as wafv2,
)
from constructs import Construct


class SecurityStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.IVpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.kms_key = kms.Key(
            self, "CmkKey",
            alias="taste-platform-cmk",
            description="Customer managed key for Taste Platform encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.kms_key.add_to_resource_policy(iam.PolicyStatement(
            actions=[
                "kms:Encrypt",
                "kms:Decrypt",
                "kms:ReEncrypt*",
                "kms:GenerateDataKey*",
                "kms:DescribeKey",
            ],
            principals=[iam.ServicePrincipal(f"logs.{Stack.of(self).region}.amazonaws.com")],
            resources=["*"],
            conditions={
                "ArnLike": {
                    "kms:EncryptionContext:aws:logs:arn":
                        f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"
                }
            },
        ))

        self.kms_key.add_to_resource_policy(iam.PolicyStatement(
            actions=[
                "kms:Encrypt",
                "kms:Decrypt",
                "kms:ReEncrypt*",
                "kms:GenerateDataKey*",
                "kms:DescribeKey",
            ],
            principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": Stack.of(self).account,
                }
            },
        ))

        self.kms_key.add_to_resource_policy(iam.PolicyStatement(
            actions=[
                "kms:Decrypt",
                "kms:GenerateDataKey*",
            ],
            principals=[iam.ServicePrincipal("sns.amazonaws.com")],
            resources=["*"],
        ))

        self.user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="taste-platform-user-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.user_pool_client = self.user_pool.add_client(
            "AppClient",
            user_pool_client_name="taste-platform-app-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            id_token_validity=Duration.hours(1),
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            generate_secret=True,
        )

        self.waf_acl = wafv2.CfnWebACL(
            self, "WafAcl",
            name="taste-platform-waf",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="taste-platform-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimit",
                    priority=1,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="taste-platform-rate-limit",
                        sampled_requests_enabled=True,
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=100,
                            aggregate_key_type="IP",
                        ),
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=2,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="taste-platform-common-rules",
                        sampled_requests_enabled=True,
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        ),
                    ),
                ),
            ],
        )
