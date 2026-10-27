"""Private network: two Availability Zones, no NAT Gateway, and the firewall rules between the parts."""

from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

DATABASE_PORT = 5432


class NetworkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Public subnets hold only the API container, which needs a route out to AWS services.
        # Private subnets (load balancer, database) have no internet route at all.
        self.vpc = ec2.Vpc(
            self, "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
            ],
        )

        # Security groups: each part accepts traffic only from the part in front of it.
        # Load balancer -> API rules are added by the API stack when it connects them, and
        # CloudFront -> load balancer by the website stack.
        self.load_balancer_sg = ec2.SecurityGroup(
            self, "LoadBalancerSg", vpc=self.vpc, description="Internal load balancer", allow_all_outbound=False,
        )
        self.api_sg = ec2.SecurityGroup(
            self, "ApiSg", vpc=self.vpc, description="API container: reached only by the load balancer",
            allow_all_outbound=True,  # ECR, Secrets Manager, Bedrock and SNS are reached over the internet.
        )
        self.database_sg = ec2.SecurityGroup(
            self, "DatabaseSg", vpc=self.vpc, description="Database: reached only by the API", allow_all_outbound=False,
        )
        self.database_sg.add_ingress_rule(self.api_sg, ec2.Port.tcp(DATABASE_PORT), "From the API")
