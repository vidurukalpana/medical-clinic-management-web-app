#!/usr/bin/env python3
"""CDK entry point. Each layer of the deployment is its own stack (see README.md)."""

import aws_cdk as cdk

from config import load_config
from stacks.api import ApiStack
from stacks.database import DatabaseStack
from stacks.network import NetworkStack
from stacks.security import SecurityStack

config = load_config()
app = cdk.App()
env = cdk.Environment(account=config.account, region=config.region)
cdk.Tags.of(app).add("Project", "CareFlow")

# Stacks in build order: security, network, database, api, website, monitoring.
security = SecurityStack(app, "CareFlow-Security", env=env, config=config)
network = NetworkStack(app, "CareFlow-Network", env=env)
database = DatabaseStack(app, "CareFlow-Database", env=env, vpc=network.vpc, database_sg=network.database_sg)
api = ApiStack(
    app, "CareFlow-Api", env=env, config=config, vpc=network.vpc,
    load_balancer_sg=network.load_balancer_sg, api_sg=network.api_sg, database_secret=database.secret,
)

app.synth()
