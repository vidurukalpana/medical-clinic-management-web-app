"""The FastAPI backend: one ARM container on Fargate behind an internal HTTPS load balancer."""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_logs as logs
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as route53_targets
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config import Config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
API_PORT = 8000
# The initial accounts the app creates on first start; each password is generated into its own secret.
INITIAL_ACCOUNTS = {
    "ADMIN": "admin",
    "DOCTOR_ONE": "doctor1",
    "DOCTOR_TWO": "doctor2",
}


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: Config, vpc: ec2.IVpc,
                 load_balancer_sg: ec2.ISecurityGroup, api_sg: ec2.ISecurityGroup,
                 database_secret: secretsmanager.ISecret, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # CloudFront reaches the private load balancer by this name, over HTTPS.
        self.origin_domain = f"origin.{config.domain_name}"
        zone = route53.HostedZone.from_hosted_zone_attributes(
            self, "Zone", hosted_zone_id=config.hosted_zone_id, zone_name=config.domain_name,
        )
        certificate = acm.Certificate(
            self, "OriginCertificate",
            domain_name=self.origin_domain,
            validation=acm.CertificateValidation.from_dns(zone),
        )

        self.load_balancer = elbv2.ApplicationLoadBalancer(
            self, "LoadBalancer",
            vpc=vpc,
            internet_facing=False,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_group=load_balancer_sg,
            drop_invalid_header_fields=True,
        )
        route53.ARecord(
            self, "OriginRecord", zone=zone, record_name=self.origin_domain,
            target=route53.RecordTarget.from_alias(route53_targets.LoadBalancerTarget(self.load_balancer)),
        )
        listener = self.load_balancer.add_listener(
            "Https", port=443, certificates=[certificate],
            ssl_policy=elbv2.SslPolicy.RECOMMENDED_TLS,
            open=False,  # Only CloudFront may connect; that rule comes with the website stack.
        )

        initial_passwords = {
            role: secretsmanager.Secret(
                self, f"{role.title().replace('_', '')}Password",
                description=f"Initial password of the '{username}' account",
                generate_secret_string=secretsmanager.SecretStringGenerator(
                    password_length=20, exclude_punctuation=True,
                ),
            )
            for role, username in INITIAL_ACCOUNTS.items()
        }

        task = ecs.FargateTaskDefinition(
            self, "Task",
            cpu=256,
            memory_limit_mib=512,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        # The root file system is read-only; /tmp is the one writable place.
        task.add_volume(name="tmp")
        container = task.add_container(
            "Api",
            image=ecs.ContainerImage.from_asset(
                str(REPOSITORY_ROOT), platform=ecr_assets.Platform.LINUX_ARM64,
            ),
            port_mappings=[ecs.PortMapping(container_port=API_PORT)],
            readonly_root_filesystem=True,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="api",
                log_group=logs.LogGroup(self, "Logs", retention=logs.RetentionDays.THREE_MONTHS),
            ),
            environment={
                "CLINIC_DEBUG": "false",
                "CLINIC_TIMEZONE": "Asia/Colombo",
                "CLINIC_DATABASE_SSL_MODE": "require",
                "CLINIC_CLIENT_ADDRESS_HEADER": "X-Viewer-Address",
                **{f"CLINIC_{role}_USERNAME": username for role, username in INITIAL_ACCOUNTS.items()},
            },
            secrets={
                "CLINIC_DATABASE_HOST": ecs.Secret.from_secrets_manager(database_secret, "host"),
                "CLINIC_DATABASE_PORT": ecs.Secret.from_secrets_manager(database_secret, "port"),
                "CLINIC_DATABASE_NAME": ecs.Secret.from_secrets_manager(database_secret, "dbname"),
                "CLINIC_DATABASE_USER": ecs.Secret.from_secrets_manager(database_secret, "username"),
                "CLINIC_DATABASE_PASSWORD": ecs.Secret.from_secrets_manager(database_secret, "password"),
                **{f"CLINIC_{role}_PASSWORD": ecs.Secret.from_secrets_manager(secret)
                   for role, secret in initial_passwords.items()},
            },
        )
        container.add_mount_points(ecs.MountPoint(source_volume="tmp", container_path="/tmp", read_only=False))

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)
        self.service = ecs.FargateService(
            self, "Service",
            cluster=cluster,
            task_definition=task,
            # One task: the rate limiter and SMS worker live in the API process (see README "Later").
            desired_count=1,
            min_healthy_percent=100,  # Start the new version before stopping the old one.
            max_healthy_percent=200,
            assign_public_ip=True,  # Reaches AWS services without a NAT Gateway; nothing can connect in.
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[api_sg],
            circuit_breaker=ecs.DeploymentCircuitBreaker(enable=True, rollback=True),
            health_check_grace_period=Duration.seconds(60),
        )
        listener.add_targets(
            "Api",
            port=API_PORT,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self.service],
            health_check=elbv2.HealthCheck(path="/", healthy_http_codes="200"),
            deregistration_delay=Duration.seconds(30),
        )

        for role, secret in initial_passwords.items():
            CfnOutput(self, f"{role.title().replace('_', '')}PasswordSecret", value=secret.secret_name,
                      description=f"Secrets Manager secret with the '{INITIAL_ACCOUNTS[role]}' password")
