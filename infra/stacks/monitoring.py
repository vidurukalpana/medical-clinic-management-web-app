"""Alarms emailed through the alert topic, and the monthly cost budget."""

from aws_cdk import Duration, Stack
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_sns as sns
from constructs import Construct

from config import Config

GIB = 1024 ** 3
FIVE_MINUTES = Duration.minutes(5)


class MonitoringStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: Config, alerts_topic: sns.ITopic,
                 load_balancer: elbv2.IApplicationLoadBalancer, target_group: elbv2.IApplicationTargetGroup,
                 service: ecs.FargateService, database: rds.IDatabaseInstance, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        notify = cloudwatch_actions.SnsAction(alerts_topic)

        def alarm(alarm_id: str, description: str, metric: cloudwatch.IMetric, threshold: float,
                  comparison: cloudwatch.ComparisonOperator, periods: int = 3,
                  missing: cloudwatch.TreatMissingData = cloudwatch.TreatMissingData.NOT_BREACHING) -> None:
            created = cloudwatch.Alarm(
                self, alarm_id,
                alarm_description=description,
                metric=metric,
                threshold=threshold,
                comparison_operator=comparison,
                evaluation_periods=periods,
                treat_missing_data=missing,
            )
            created.add_alarm_action(notify)
            created.add_ok_action(notify)  # A second email when it is back to normal.

        above = cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        below = cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD

        # The website's API.
        alarm("ApiDown", "The API has no healthy container: patients cannot book and staff cannot sign in.",
              target_group.metrics.healthy_host_count(period=Duration.minutes(1), statistic="Minimum"),
              1, below, missing=cloudwatch.TreatMissingData.BREACHING)
        alarm("ApiErrors", "The API returned more than 10 server errors in 5 minutes, 3 times in a row.",
              load_balancer.metrics.http_code_target(elbv2.HttpCodeTarget.TARGET_5XX_COUNT, period=FIVE_MINUTES),
              10, above)
        alarm("ApiCpuHigh", "The API container's CPU has been above 80% for 15 minutes.",
              service.metric_cpu_utilization(period=FIVE_MINUTES), 80, above)
        alarm("ApiMemoryHigh", "The API container's memory has been above 85% for 15 minutes.",
              service.metric_memory_utilization(period=FIVE_MINUTES), 85, above)

        # The database.
        alarm("DatabaseCpuHigh", "The database CPU has been above 80% for 15 minutes.",
              database.metric_cpu_utilization(period=FIVE_MINUTES), 80, above)
        alarm("DatabaseStorageLow", "The database has less than 2 GB of free storage.",
              database.metric_free_storage_space(period=FIVE_MINUTES), 2 * GIB, below, periods=1)
        alarm("DatabaseMemoryLow", "The database has had less than 100 MB of free memory for 15 minutes.",
              database.metric_freeable_memory(period=FIVE_MINUTES), 100 * 1024 ** 2, below)

        # The whole AWS bill: emails at 80% and 100% of the monthly budget.
        budgets.CfnBudget(
            self, "MonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name="CareFlow monthly",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=config.monthly_budget_usd, unit="USD"),
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type="ACTUAL", comparison_operator="GREATER_THAN",
                        threshold=percent, threshold_type="PERCENTAGE",
                    ),
                    subscribers=[budgets.CfnBudget.SubscriberProperty(
                        subscription_type="EMAIL", address=config.alert_email,
                    )],
                )
                for percent in (80, 100)
            ],
        )
