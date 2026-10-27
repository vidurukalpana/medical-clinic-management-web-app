"""Account-wide security: an audit log of every AWS action, threat detection, and the alert email."""

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudtrail as cloudtrail
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_guardduty as guardduty
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct

from config import Config

AUDIT_LOG_DAYS = 365
# GuardDuty severity: 4-6.9 medium, 7+ high. Low findings are informational and would only add noise.
MIN_ALERT_SEVERITY = 4


class SecurityStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # One email topic for every alert: GuardDuty here, alarms and the budget in later stacks.
        # AWS sends a confirmation email that must be accepted before alerts arrive.
        self.alerts_topic = sns.Topic(self, "Alerts", display_name="CareFlow alerts")
        self.alerts_topic.add_subscription(subscriptions.EmailSubscription(config.alert_email))

        # CloudTrail: who changed what in the account. Kept after `destroy.sh`, as audit records.
        audit_bucket = s3.Bucket(
            self, "AuditLogs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            lifecycle_rules=[s3.LifecycleRule(
                expiration=Duration.days(AUDIT_LOG_DAYS),
                noncurrent_version_expiration=Duration.days(1),
            )],
            removal_policy=RemovalPolicy.RETAIN,
        )
        cloudtrail.Trail(
            self, "AuditTrail",
            bucket=audit_bucket,
            is_multi_region_trail=True,
            include_global_service_events=True,
            enable_file_validation=True,  # Detects any change to a log file after it was written.
        )

        # GuardDuty: watches account activity and database logins for signs of attack.
        guardduty.CfnDetector(
            self, "ThreatDetection",
            enable=True,
            features=[guardduty.CfnDetector.CFNFeatureConfigurationProperty(name="RDS_LOGIN_EVENTS", status="ENABLED")],
        )
        events.Rule(
            self, "ThreatAlert",
            event_pattern=events.EventPattern(
                source=["aws.guardduty"],
                detail_type=["GuardDuty Finding"],
                detail={"severity": [{"numeric": [">=", MIN_ALERT_SEVERITY]}]},
            ),
            targets=[targets.SnsTopic(self.alerts_topic, message=events.RuleTargetInput.from_text(
                f"GuardDuty found a possible security problem (severity "
                f"{events.EventField.from_path('$.detail.severity')}): "
                f"{events.EventField.from_path('$.detail.title')}. "
                f"Region {events.EventField.from_path('$.region')}. "
                "Open GuardDuty in the AWS console for details."
            ))],
        )
