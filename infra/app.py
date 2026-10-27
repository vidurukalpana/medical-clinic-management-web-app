#!/usr/bin/env python3
"""CDK entry point. Each layer of the deployment is its own stack (see README.md)."""

import aws_cdk as cdk

from config import load_config
from stacks.api import ApiStack
from stacks.database import DatabaseStack
from stacks.edge import EdgeStack
from stacks.network import NetworkStack
from stacks.security import SecurityStack
from stacks.website import WebsiteStack

config = load_config()
app = cdk.App()
env = cdk.Environment(account=config.account, region=config.region)
# CloudFront only accepts certificates and WAF rules from us-east-1.
edge_env = cdk.Environment(account=config.account, region="us-east-1")
cdk.Tags.of(app).add("Project", "CareFlow")

# Stacks in build order: security, network, database, api, edge + website, monitoring.
security = SecurityStack(app, "CareFlow-Security", env=env, config=config)
network = NetworkStack(app, "CareFlow-Network", env=env)
database = DatabaseStack(app, "CareFlow-Database", env=env, vpc=network.vpc, database_sg=network.database_sg)
api = ApiStack(
    app, "CareFlow-Api", env=env, config=config, vpc=network.vpc,
    load_balancer_sg=network.load_balancer_sg, api_sg=network.api_sg, database_secret=database.secret,
)
edge = EdgeStack(app, "CareFlow-Edge", env=edge_env, config=config, cross_region_references=True)
website = WebsiteStack(
    app, "CareFlow-Website", env=env, config=config, cross_region_references=True,
    certificate=edge.certificate, web_acl_arn=edge.web_acl_arn,
    load_balancer=api.load_balancer, origin_domain=api.origin_domain,
    vpc=network.vpc, load_balancer_sg=network.load_balancer_sg,
)

app.synth()
