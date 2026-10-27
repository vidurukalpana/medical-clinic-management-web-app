"""CloudFront in front of everything: the React app from S3, and /api/* to the private load balancer."""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as route53_targets
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import Config

FRONTEND_BUILD = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# Sends www to the main domain, and app pages such as /staff to the React app's index.html.
WEBSITE_FUNCTION = """
function handler(event) {
  var request = event.request;
  var host = request.headers.host ? request.headers.host.value : "";
  if (host.indexOf("www.") === 0) {
    return {
      statusCode: 301,
      statusDescription: "Moved Permanently",
      headers: { location: { value: "https://" + host.substring(4) + request.uri } },
    };
  }
  if (request.uri.split("/").pop().indexOf(".") === -1) {
    request.uri = "/index.html";
  }
  return request;
}
"""

# The visitor's address for the API's rate limits. Replaces any value the visitor sent.
API_FUNCTION = """
function handler(event) {
  var request = event.request;
  request.headers["x-viewer-address"] = { value: event.viewer.ip };
  return request;
}
"""

# Google Fonts for the typeface; inline styles for the check-in QR code's SVG. No inline scripts.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class WebsiteStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: Config,
                 certificate: acm.ICertificate, web_acl_arn: str,
                 load_balancer: elbv2.IApplicationLoadBalancer, origin_domain: str,
                 vpc: ec2.IVpc, load_balancer_sg: ec2.ISecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not (FRONTEND_BUILD / "index.html").exists():
            raise SystemExit("frontend/dist is missing. Build the React app first (deploy.sh does this).")

        bucket = s3.Bucket(
            self, "WebsiteFiles",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            # Only built files live here; they are uploaded again on every deploy.
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        headers = cloudfront.ResponseHeadersPolicy(
            self, "SecurityHeaders",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365), include_subdomains=True, override=True,
                ),
                content_security_policy=cloudfront.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=CONTENT_SECURITY_POLICY, override=True,
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY, override=True,
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override=True,
                ),
            ),
        )

        def viewer_request(name: str, code: str) -> list[cloudfront.FunctionAssociation]:
            function = cloudfront.Function(
                self, name, code=cloudfront.FunctionCode.from_inline(code),
                runtime=cloudfront.FunctionRuntime.JS_2_0,
            )
            return [cloudfront.FunctionAssociation(
                function=function, event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
            )]

        api_origin = origins.VpcOrigin.with_application_load_balancer(
            load_balancer,
            domain_name=origin_domain,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
            origin_ssl_protocols=[cloudfront.OriginSslPolicy.TLS_V1_2],
            read_timeout=Duration.seconds(60),  # The chat assistant can take up to a minute.
        )
        self.distribution = cloudfront.Distribution(
            self, "Distribution",
            domain_names=[config.domain_name, f"www.{config.domain_name}"],
            certificate=certificate,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            web_acl_id=web_acl_arn,
            price_class=cloudfront.PriceClass.PRICE_CLASS_200,  # Includes edge locations in India.
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=headers,
                function_associations=viewer_request("WebsiteFunction", WEBSITE_FUNCTION),
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    # Not the Host header: the load balancer's certificate is for the origin name.
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    response_headers_policy=headers,
                    function_associations=viewer_request("ApiFunction", API_FUNCTION),
                ),
            },
        )

        # The load balancer accepts HTTPS only from the security group CloudFront creates for its
        # private (VPC origin) connections, which exists once the distribution is deployed.
        cloudfront_sg = cr.AwsCustomResource(
            self, "CloudFrontSecurityGroup",
            on_update=cr.AwsSdkCall(
                service="EC2",
                action="describeSecurityGroups",
                parameters={"Filters": [
                    {"Name": "group-name", "Values": ["CloudFront-VPCOrigins-Service-SG*"]},
                    {"Name": "vpc-id", "Values": [vpc.vpc_id]},
                ]},
                physical_resource_id=cr.PhysicalResourceId.of("cloudfront-vpc-origins-sg"),
                output_paths=["SecurityGroups.0.GroupId"],
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE),
            install_latest_aws_sdk=False,
        )
        cloudfront_sg.node.add_dependency(self.distribution)
        ec2.CfnSecurityGroupIngress(
            self, "LoadBalancerFromCloudFront",
            group_id=load_balancer_sg.security_group_id,
            ip_protocol="tcp", from_port=443, to_port=443,
            source_security_group_id=cloudfront_sg.get_response_field("SecurityGroups.0.GroupId"),
            description="HTTPS from CloudFront",
        )

        s3deploy.BucketDeployment(
            self, "UploadWebsite",
            sources=[s3deploy.Source.asset(str(FRONTEND_BUILD))],
            destination_bucket=bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            # Browsers check for a newer version on each visit; CloudFront still serves from its cache.
            cache_control=[s3deploy.CacheControl.no_cache()],
            memory_limit=512,
        )

        zone = route53.HostedZone.from_hosted_zone_attributes(
            self, "Zone", hosted_zone_id=config.hosted_zone_id, zone_name=config.domain_name,
        )
        target = route53.RecordTarget.from_alias(route53_targets.CloudFrontTarget(self.distribution))
        for record_id, name in (("Apex", config.domain_name), ("Www", f"www.{config.domain_name}")):
            route53.ARecord(self, f"{record_id}A", zone=zone, record_name=name, target=target)
            route53.AaaaRecord(self, f"{record_id}Aaaa", zone=zone, record_name=name, target=target)

        CfnOutput(self, "WebsiteUrl", value=f"https://{config.domain_name}")
