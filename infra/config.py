"""Deployment settings, read from the environment that cdk.sh loads from infra/.env."""

import os
from dataclasses import dataclass

REQUIRED = ("DOMAIN_NAME", "HOSTED_ZONE_ID", "ALERT_EMAIL")


@dataclass(frozen=True)
class Config:
    account: str | None  # Filled in by the CDK CLI from the AWS credentials.
    region: str
    domain_name: str
    hosted_zone_id: str  # Route 53 hosted zone of the domain, created when the domain was registered.
    alert_email: str
    monthly_budget_usd: int


def load_config() -> Config:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Set {', '.join(missing)} in infra/.env (see .env.example).")
    return Config(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("AWS_REGION", "ap-south-1"),
        domain_name=os.environ["DOMAIN_NAME"],
        hosted_zone_id=os.environ["HOSTED_ZONE_ID"],
        alert_email=os.environ["ALERT_EMAIL"],
        monthly_budget_usd=int(os.environ.get("MONTHLY_BUDGET_USD", "100")),
    )
