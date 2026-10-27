#!/usr/bin/env python3
"""CDK entry point. Each layer of the deployment is its own stack (see README.md)."""

import aws_cdk as cdk

from config import load_config

config = load_config()
app = cdk.App()
env = cdk.Environment(account=config.account, region=config.region)
cdk.Tags.of(app).add("Project", "CareFlow")

# Stacks are added here in build order: security, network, database, api, website, monitoring.

app.synth()
