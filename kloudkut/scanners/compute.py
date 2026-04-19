"""Compute scanners: EC2, Lambda, ECS, EKS, EMR, Glue, Lightsail, CodeBuild."""
import logging
from datetime import datetime, timedelta, UTC
from botocore.exceptions import ClientError
from kloudkut.core import BaseScanner, Finding, get_client, get_avg, get_sum, ec2_monthly, eks_monthly
from kloudkut.core.pricing import downsize_suggestion

logger = logging.getLogger(__name__)


def _excluded(tags: list, exclude_tags: dict) -> bool:
    tag_map = {t["Key"]: t["Value"] for t in tags}
    return any(tag_map.get(k) == v for k, v in exclude_tags.items())


class EC2Scanner(BaseScanner):
    service = "EC2"

    def scan_region(self, region):
        findings = []
        ec2 = get_client("ec2", region)
        exclude_tags = self.config.get("exclude_tags", {})

        for page in ec2.get_paginator("describe_instances").paginate():
            for r in page["Reservations"]:
                for i in r["Instances"]:
                    if i["State"]["Name"] not in ("running", "stopped"):
                        continue
                    tags = i.get("Tags", [])
                    if _excluded(tags, exclude_tags):
                        continue
                    iid = i["InstanceId"]
                    itype = i.get("InstanceType", "")
                    name = next((t["Value"] for t in tags if t["Key"] == "Name"), iid)
                    monthly = ec2_monthly(itype)

                    if i["State"]["Name"] == "stopped":
                        findings.append(Finding(iid, name, "EC2", region,
                                                f"Stopped instance ({itype}) — still incurring EBS storage charges. Terminate if no longer needed, or snapshot & delete volumes",
                                                ec2_monthly(itype, region),
                                                {"instance_type": itype, "console_url":
                                                 f"https://{region}.console.aws.amazon.com/ec2/v2/home?region={region}#Instances:instanceId={iid}"},
                                                remediation=f"aws ec2 terminate-instances --instance-ids {iid} --region {region}"))
                        continue

                    avg_cpu = get_avg(region, "AWS/EC2", "CPUUtilization", "InstanceId", iid, self.cw_days, self.cw_period)
                    net_in = get_sum(region, "AWS/EC2", "NetworkIn", "InstanceId", iid, self.cw_days, self.cw_period)
                    net_out = get_sum(region, "AWS/EC2", "NetworkOut", "InstanceId", iid, self.cw_days, self.cw_period)
                    monthly = ec2_monthly(itype, region)

                    if avg_cpu < self.config.get("avgCpu", 1) and (net_in + net_out) < self.config.get("netInOut", 5000):
                        waste = round(monthly * (1 - avg_cpu / 100), 2)
                        findings.append(Finding(iid, name, "EC2", region,
                                                f"Idle instance ({itype}) — avg CPU {avg_cpu:.1f}% over {self.cw_days}d with near-zero network. You're paying full On-Demand rate for an unused instance. Stop or terminate it",
                                                waste,
                                                {"instance_type": itype, "cpu": avg_cpu,
                                                 "network": net_in + net_out,
                                                 "console_url": f"https://{region}.console.aws.amazon.com/ec2/v2/home?region={region}#Instances:instanceId={iid}"},
                                                remediation=f"aws ec2 stop-instances --instance-ids {iid} --region {region}"))
                    elif avg_cpu < self.config.get("rightsizeCpu", 20) and downsize_suggestion(itype):
                        # Right-sizing: instance is oversized but not idle
                        smaller = downsize_suggestion(itype)
                        saving = round(ec2_monthly(itype, region) - ec2_monthly(smaller, region), 2)
                        if saving > 0:
                            findings.append(Finding(iid, name, "EC2", region,
                                                    f"Oversized ({itype}, CPU {avg_cpu:.1f}% over {self.cw_days}d) — downsize to {smaller} for same workload at lower cost",
                                                    saving,
                                                    {"instance_type": itype, "suggested_type": smaller, "cpu": avg_cpu,
                                                     "console_url": f"https://{region}.console.aws.amazon.com/ec2/v2/home?region={region}#Instances:instanceId={iid}"},
                                                    remediation=f"aws ec2 modify-instance-attribute --instance-id {iid} --instance-type {{\"Value\":\"{smaller}\"}} --region {region}"))
        return findings


class LambdaScanner(BaseScanner):
    service = "LAMBDA"

    def scan_region(self, region):
        findings = []
        lmb = get_client("lambda", region)
        exclude_tags = self.config.get("exclude_tags", {})

        for page in lmb.get_paginator("list_functions").paginate():
            for fn in page["Functions"]:
                name = fn["FunctionName"]
                try:
                    tags = lmb.list_tags(Resource=fn["FunctionArn"]).get("Tags", {})
                    if any(tags.get(k) == v for k, v in exclude_tags.items()):
                        continue
                except ClientError as e:
                    logger.debug("Lambda list_tags failed for %s: %s", name, e)
                invocations = get_sum(region, "AWS/Lambda", "Invocations", "FunctionName", name, self.cw_days, self.cw_period)
                if invocations <= self.config.get("invocations", 0):
                    findings.append(Finding(name, name, "Lambda", region,
                                            f"Zero invocations in {self.cw_days}d — function is deployed but never called. Associated CloudWatch Logs and provisioned concurrency (if any) still incur charges. Delete if obsolete",
                                            5.0,
                                            {"console_url": f"https://{region}.console.aws.amazon.com/lambda/home?region={region}#/functions/{name}"}))
        return findings


class ECSScanner(BaseScanner):
    service = "ECS"

    def scan_region(self, region):
        findings = []
        ecs = get_client("ecs", region)

        for page in ecs.get_paginator("list_clusters").paginate():
            for cluster_arn in page.get("clusterArns", []):
                svc_arns = [arn
                             for sp in ecs.get_paginator("list_services").paginate(cluster=cluster_arn)
                             for arn in sp.get("serviceArns", [])]
                if not svc_arns:
                    continue
                for i in range(0, len(svc_arns), 10):
                    for svc in ecs.describe_services(cluster=cluster_arn, services=svc_arns[i:i+10]).get("services", []):
                        if svc["runningCount"] == 0:
                            findings.append(Finding(svc["serviceName"], svc["serviceName"], "ECS", region,
                                                    f"Service has 0 running tasks (desired: {svc['desiredCount']}) — the cluster and service definition still cost overhead. Scale down or delete if no longer needed",
                                                    svc["desiredCount"] * 30.0))
        return findings


class EKSScanner(BaseScanner):
    service = "EKS"

    def scan_region(self, region):
        findings = []
        eks = get_client("eks", region)

        for page in eks.get_paginator("list_clusters").paginate():
            for name in page.get("clusters", []):
                cluster = eks.describe_cluster(name=name)["cluster"]
                nodegroups = eks.list_nodegroups(clusterName=name).get("nodegroups", [])
                if not nodegroups or cluster["status"] != "ACTIVE":
                    findings.append(Finding(name, name, "EKS", region,
                                            f"EKS cluster with no active node groups — the control plane charges $0.10/hr ($73/mo) even with zero workloads. Delete if unused",
                                            eks_monthly()))
        return findings


class EMRScanner(BaseScanner):
    service = "EMR"

    def scan_region(self, region):
        findings = []
        emr = get_client("emr", region)

        for page in emr.get_paginator("list_clusters").paginate(ClusterStates=["RUNNING", "WAITING"]):
            for cluster in page.get("Clusters", []):
                cid = cluster["Id"]
                is_idle = get_avg(region, "AWS/ElasticMapReduce", "IsIdle", "JobFlowId", cid, self.cw_days, self.cw_period)
                if is_idle > self.config.get("idle_threshold", 0.8):
                    findings.append(Finding(cid, cluster["Name"], "EMR", region,
                                            f"Cluster idle {is_idle*100:.0f}% of the last {self.cw_days}d — running EC2 instances in the cluster still incur full hourly charges. Terminate or enable auto-termination",
                                            500.0))
        return findings


class GlueScanner(BaseScanner):
    service = "GLUE"

    def scan_region(self, region):
        findings = []
        glue = get_client("glue", region)
        days = self.config.get("days", 30)

        for page in glue.get_paginator("get_jobs").paginate():
            for job in page.get("Jobs", []):
                name = job["Name"]
                runs = glue.get_job_runs(JobName=name, MaxResults=5).get("JobRuns", [])
                if not any(r["StartedOn"] > datetime.now(UTC) - timedelta(days=days) for r in runs):
                    capacity = job.get("MaxCapacity", 2)
                    findings.append(Finding(name, name, "Glue", region,
                                            f"No job runs in {days}d (capacity: {capacity} DPU) — job definition exists but is never triggered. Delete or disable if obsolete to avoid accidental runs",
                                            capacity * 0.44 * 10))
        return findings


class LightsailScanner(BaseScanner):
    service = "LIGHTSAIL"

    def is_enabled(self, region):
        try:
            get_client("lightsail", region).get_regions()
            return True
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDeniedException",):
                return True
            # Lightsail not available in this region
            return False
        except Exception:
            # Catch connection errors (EndpointConnectionError, etc.) for
            # regions where Lightsail has no endpoint at all
            return False

    def scan_region(self, region):
        findings = []
        try:
            findings = [Finding(inst["name"], inst["name"], "Lightsail", region,
                                "Stopped Lightsail instance — you're still billed the fixed monthly plan rate even while stopped. Delete or create a snapshot & terminate",
                                3.5)
                        for inst in get_client("lightsail", region).get_instances().get("instances", [])
                        if inst["state"]["name"] == "stopped"]
        except ClientError as e:
            logger.debug("Lightsail not available in %s: %s", region, e)
        return findings


class CodeBuildScanner(BaseScanner):
    service = "CODEBUILD"

    def scan_region(self, region):
        findings = []
        cb = get_client("codebuild", region)
        days = self.config.get("days", 90)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        for page in cb.get_paginator("list_projects").paginate():
            for name in page.get("projects", []):
                ids = cb.list_builds_for_project(projectName=name).get("ids", [])
                if not ids or not any(b.get("startTime", cutoff) > cutoff
                                      for b in cb.batch_get_builds(ids=ids[:5]).get("builds", [])):
                    findings.append(Finding(name, name, "CodeBuild", region,
                                            f"No builds triggered in {days}d — project exists but is inactive. Delete if CI/CD pipeline has moved elsewhere",
                                            1.0))
        return findings
