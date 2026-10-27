"""The HTTPS certificate and WAF rules for CloudFront, which must live in us-east-1."""

from aws_cdk import Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

from config import Config

# Per visitor address, per 5 minutes. Staff behind one clinic connection share this, and
# the live queue and dashboard refresh every 20 seconds, so it is set well above normal use.
API_REQUESTS_PER_5_MINUTES = 2000


def _visibility(name: str) -> wafv2.CfnWebACL.VisibilityConfigProperty:
    return wafv2.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True, metric_name=name, sampled_requests_enabled=True,
    )


def _aws_managed_rules(name: str, priority: int) -> wafv2.CfnWebACL.RuleProperty:
    return wafv2.CfnWebACL.RuleProperty(
        name=name,
        priority=priority,
        override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
        statement=wafv2.CfnWebACL.StatementProperty(
            managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(vendor_name="AWS", name=name),
        ),
        visibility_config=_visibility(name),
    )


class EdgeStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        zone = route53.HostedZone.from_hosted_zone_attributes(
            self, "Zone", hosted_zone_id=config.hosted_zone_id, zone_name=config.domain_name,
        )
        self.certificate = acm.Certificate(
            self, "Certificate",
            domain_name=config.domain_name,
            subject_alternative_names=[f"www.{config.domain_name}"],
            validation=acm.CertificateValidation.from_dns(zone),
        )

        rate_limit = wafv2.CfnWebACL.RuleProperty(
            name="ApiRateLimit",
            priority=0,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=API_REQUESTS_PER_5_MINUTES,
                    aggregate_key_type="IP",
                    evaluation_window_sec=300,
                    scope_down_statement=wafv2.CfnWebACL.StatementProperty(
                        byte_match_statement=wafv2.CfnWebACL.ByteMatchStatementProperty(
                            field_to_match=wafv2.CfnWebACL.FieldToMatchProperty(uri_path={}),
                            positional_constraint="STARTS_WITH",
                            search_string="/api/",
                            text_transformations=[wafv2.CfnWebACL.TextTransformationProperty(priority=0, type="NONE")],
                        ),
                    ),
                ),
            ),
            visibility_config=_visibility("ApiRateLimit"),
        )
        web_acl = wafv2.CfnWebACL(
            self, "WebAcl",
            scope="CLOUDFRONT",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=_visibility("CareFlowWebAcl"),
            rules=[
                rate_limit,
                _aws_managed_rules("AWSManagedRulesAmazonIpReputationList", 1),
                _aws_managed_rules("AWSManagedRulesCommonRuleSet", 2),
                _aws_managed_rules("AWSManagedRulesKnownBadInputsRuleSet", 3),
            ],
        )
        self.web_acl_arn = web_acl.attr_arn
