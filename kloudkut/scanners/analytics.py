"""Analytics, messaging, and management scanners."""
from datetime import datetime, timedelta, UTC
from kloudkut.core import BaseScanner, Finding, get_client, get_sum, sagemaker_monthly


class KinesisScanner(BaseScanner):
    service = "KINESIS"

    def scan_region(self, region):
        findings = []
        kinesis = get_client("kinesis", region)
        for page in kinesis.get_paginator("list_streams").paginate():
            for name in page.get("StreamNames", []):
                records = get_sum(region, "AWS/Kinesis", "IncomingRecords", "StreamName", name, self.cw_days, self.cw_period)
                if records < self.config.get("min_records", 100):
                    shards = len(kinesis.describe_stream(StreamName=name)["StreamDescription"]["Shards"])
                    findings.append(Finding(name, name, "Kinesis", region, f"Records={records:.0f}", shards * 11.0))
        return findings


class SQSScanner(BaseScanner):
    service = "SQS"

    def scan_region(self, region):
        findings = []
        sqs = get_client("sqs", region)
        for page in sqs.get_paginator("list_queues").paginate():
            for url in page.get("QueueUrls", []):
                name = url.split("/")[-1]
                sent = get_sum(region, "AWS/SQS", "NumberOfMessagesSent", "QueueName", name, self.cw_days, self.cw_period)
                received = get_sum(region, "AWS/SQS", "NumberOfMessagesReceived", "QueueName", name, self.cw_days, self.cw_period)
                if sent == 0 and received == 0:
                    findings.append(Finding(name, name, "SQS", region, "No messages", 0.5))
        return findings


class SNSScanner(BaseScanner):
    service = "SNS"

    def scan_region(self, region):
        findings = []
        sns = get_client("sns", region)
        for page in sns.get_paginator("list_topics").paginate():
            for topic in page.get("Topics", []):
                name = topic["TopicArn"].split(":")[-1]
                published = get_sum(region, "AWS/SNS", "NumberOfMessagesPublished", "TopicName", name, self.cw_days, self.cw_period)
                if published == 0:
                    findings.append(Finding(name, name, "SNS", region, "No messages published", 0.5))
        return findings


class StepFunctionsScanner(BaseScanner):
    service = "STEPFUNCTIONS"

    def scan_region(self, region):
        findings = []
        sf = get_client("stepfunctions", region)
        for page in sf.get_paginator("list_state_machines").paginate():
            for sm in page.get("stateMachines", []):
                arn, name = sm["stateMachineArn"], sm["name"]
                started = get_sum(region, "AWS/States", "ExecutionsStarted", "StateMachineArn", arn, self.cw_days, self.cw_period)
                if started == 0:
                    findings.append(Finding(name, name, "Step Functions", region, "No executions", 25.0))
        return findings


class SageMakerScanner(BaseScanner):
    service = "SAGEMAKER"

    def scan_region(self, region):
        findings = []
        sm = get_client("sagemaker", region)
        for page in sm.get_paginator("list_endpoints").paginate():
            for ep in page.get("Endpoints", []):
                name = ep["EndpointName"]
                invocations = get_sum(region, "AWS/SageMaker", "Invocations", "EndpointName", name, self.cw_days, self.cw_period)
                if invocations == 0:
                    try:
                        cfg = sm.describe_endpoint(EndpointName=name)
                        itype = cfg.get("ProductionVariants", [{}])[0].get("CurrentInstanceType", "ml.m5.xlarge")
                        monthly = sagemaker_monthly(itype)
                    except Exception:
                        monthly = sagemaker_monthly("ml.m5.xlarge")
                    findings.append(Finding(name, name, "SageMaker", region, "No invocations", monthly))
        return findings


class AthenaScanner(BaseScanner):
    service = "ATHENA"

    def scan_region(self, region):
        findings = []
        athena = get_client("athena", region)
        for page in athena.get_paginator("list_work_groups").paginate():
            for wg in page.get("WorkGroups", []):
                name = wg["Name"]
                if not athena.list_query_executions(WorkGroup=name, MaxResults=5).get("QueryExecutionIds"):
                    findings.append(Finding(name, name, "Athena", region, "No queries", 5.0))
        return findings


class CloudFormationScanner(BaseScanner):
    service = "CLOUDFORMATION"

    def scan_region(self, region):
        findings = []
        cfn = get_client("cloudformation", region)
        for page in cfn.get_paginator("list_stacks").paginate(
            StackStatusFilter=["CREATE_FAILED", "ROLLBACK_COMPLETE", "DELETE_FAILED"]
        ):
            for stack in page.get("StackSummaries", []):
                findings.append(Finding(stack["StackName"], stack["StackName"], "CloudFormation", region,
                                        f"Status: {stack['StackStatus']}", 1.0))
        return findings


class EventBridgeScanner(BaseScanner):
    service = "EVENTBRIDGE"

    def scan_region(self, region):
        findings = []
        for page in get_client("events", region).get_paginator("list_rules").paginate():
            for rule in page.get("Rules", []):
                if rule["State"] == "DISABLED":
                    findings.append(Finding(rule["Name"], rule["Name"], "EventBridge", region, "Disabled rule", 0.5))
        return findings


class CloudWatchAlarmsScanner(BaseScanner):
    service = "CLOUDWATCH_ALARMS"

    def scan_region(self, region):
        findings = []
        for page in get_client("cloudwatch", region).get_paginator("describe_alarms").paginate():
            for alarm in page.get("MetricAlarms", []):
                if alarm["StateValue"] == "INSUFFICIENT_DATA":
                    findings.append(Finding(alarm["AlarmName"], alarm["AlarmName"], "CloudWatch Alarm",
                                            region, "Insufficient data", 0.1))
        return findings


class CloudWatchLogsScanner(BaseScanner):
    service = "CLOUDWATCH_LOGS"

    def scan_region(self, region):
        findings = []
        logs = get_client("logs", region)
        days = self.config.get("days_since_last_event", 90)
        threshold = int((datetime.now(UTC) - timedelta(days=days)).timestamp() * 1000)

        for page in logs.get_paginator("describe_log_groups").paginate():
            for lg in page.get("logGroups", []):
                if lg.get("lastIngestionTime", 0) < threshold:
                    size_mb = lg.get("storedBytes", 0) / (1024 * 1024)
                    findings.append(Finding(lg["logGroupName"], lg["logGroupName"], "CloudWatch Logs", region,
                                            f"No events in {days}d", round(size_mb * 0.03, 2)))
        return findings
