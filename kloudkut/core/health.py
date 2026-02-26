"""Health checks and system status."""
import boto3
from datetime import datetime, UTC
from typing import Dict

def check_aws_credentials() -> Dict:
    """Check if AWS credentials are valid."""
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        return {
            "status": "healthy",
            "account_id": identity["Account"],
            "arn": identity["Arn"]
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_aws_permissions() -> Dict:
    """Check if required AWS permissions are available."""
    required_services = ["ec2", "rds", "s3", "cloudwatch"]
    results = {}
    for service in required_services:
        try:
            client = boto3.client(service, region_name="us-east-1")
            if service == "ec2":
                client.describe_regions(DryRun=True)
            elif service == "rds":
                client.describe_db_instances(MaxRecords=1)
            elif service == "s3":
                client.list_buckets()
            elif service == "cloudwatch":
                client.list_metrics(MaxRecords=1)
            results[service] = "accessible"
        except client.exceptions.DryRunOperation:
            results[service] = "accessible"
        except Exception as e:
            if "UnauthorizedOperation" in str(e) or "AccessDenied" in str(e):
                results[service] = "no_permission"
            else:
                results[service] = f"error: {str(e)[:50]}"
    return results

def get_system_status() -> Dict:
    """Get overall system health status."""
    creds = check_aws_credentials()
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "credentials": creds,
        "status": "healthy" if creds["status"] == "healthy" else "unhealthy"
    }
