"""PostgreSQL on RDS: Multi-AZ, encrypted, TLS only, 35 days of point-in-time backups."""

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct

DATABASE_NAME = "medical_clinic"
DATABASE_USER = "clinic_app"
# Characters that would need escaping in the connection URL or the shell.
PASSWORD_EXCLUDED_CHARACTERS = " %+~`#$&*()|[]{}:;<>?!'/@\"\\"


class DatabaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, vpc: ec2.IVpc,
                 database_sg: ec2.ISecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        engine = rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_17)
        parameters = rds.ParameterGroup(
            self, "Parameters", engine=engine,
            parameters={"rds.force_ssl": "1"},  # Refuse unencrypted connections.
        )

        # destroy.sh sets this context value; otherwise deletion protection stays on.
        allow_deletion = self.node.try_get_context("allowDatabaseDeletion") == "true"

        self.instance = rds.DatabaseInstance(
            self, "Database",
            engine=engine,
            parameter_group=parameters,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO),
            multi_az=True,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[database_sg],
            publicly_accessible=False,
            database_name=DATABASE_NAME,
            credentials=rds.Credentials.from_generated_secret(
                DATABASE_USER, exclude_characters=PASSWORD_EXCLUDED_CHARACTERS,
            ),
            storage_type=rds.StorageType.GP3,
            allocated_storage=20,
            max_allocated_storage=100,
            storage_encrypted=True,
            # Times in UTC: 00:30-01:30 and Sunday 02:00-02:30 in Sri Lanka, when the clinic is closed.
            backup_retention=Duration.days(35),
            preferred_backup_window="19:00-20:00",
            preferred_maintenance_window="Sat:20:30-Sat:21:00",
            delete_automated_backups=False,
            auto_minor_version_upgrade=True,
            deletion_protection=not allow_deletion,
            removal_policy=RemovalPolicy.SNAPSHOT,
        )
        self.secret = self.instance.secret
