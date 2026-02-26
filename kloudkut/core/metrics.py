"""CloudWatch metrics helpers."""
from datetime import datetime, timedelta, UTC
from kloudkut.core.aws import get_client


def _query(region, namespace, metric, dims, days, period, stat) -> list[float]:
    end = datetime.now(UTC)
    resp = get_client("cloudwatch", region).get_metric_statistics(
        Namespace=namespace, MetricName=metric, Dimensions=dims,
        StartTime=end - timedelta(days=days), EndTime=end,
        Period=period, Statistics=[stat],
    )
    return [dp[stat] for dp in resp.get("Datapoints", [])]


def get_sum(region, namespace, metric, dim_name, dim_val, days=14, period=1209600) -> float:
    pts = _query(region, namespace, metric, [{"Name": dim_name, "Value": dim_val}], days, period, "Sum")
    return sum(pts) if pts else 0.0


def get_avg(region, namespace, metric, dim_name, dim_val, days=14, period=1209600) -> float:
    pts = _query(region, namespace, metric, [{"Name": dim_name, "Value": dim_val}], days, period, "Average")
    return sum(pts) / len(pts) if pts else 0.0
