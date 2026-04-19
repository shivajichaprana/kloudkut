"""Database scanners: RDS, DynamoDB, Redshift, ElastiCache, DocumentDB, Aurora, OpenSearch, MSK."""
from kloudkut.core import (
    BaseScanner, Finding, get_client, get_avg, get_sum,
    rds_monthly, redshift_monthly, elasticache_monthly,
    opensearch_monthly, msk_monthly, documentdb_monthly, aurora_monthly,
)
from kloudkut.core.pricing import downsize_suggestion


class RDSScanner(BaseScanner):
    service = "RDS"

    def scan_region(self, region):
        findings = []
        rds = get_client("rds", region)
        exclude_tags = self.config.get("exclude_tags", {})

        for page in rds.get_paginator("describe_db_instances").paginate():
            for db in page.get("DBInstances", []):
                tags = {t["Key"]: t["Value"] for t in db.get("TagList", [])}
                if any(tags.get(k) == v for k, v in exclude_tags.items()):
                    continue
                dbid = db["DBInstanceIdentifier"]
                conns = get_avg(region, "AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", dbid, self.cw_days, self.cw_period)
                if conns <= self.config.get("connectionCount", 0):
                    iclass = db.get("DBInstanceClass", "db.t3.micro")
                    multi_az = db.get("MultiAZ", False)
                    monthly = rds_monthly(iclass, multi_az, region)
                    az_note = " (Multi-AZ doubles cost)" if multi_az else ""
                    findings.append(Finding(dbid, dbid, "RDS", region,
                                            f"Zero database connections over {self.cw_days}d ({iclass}{az_note}) — instance is running and billed hourly even with no clients connected. Stop or snapshot & delete if unused",
                                            monthly,
                                            {"instance_class": iclass, "connections": conns,
                                             "console_url": f"https://{region}.console.aws.amazon.com/rds/home?region={region}#database:id={dbid}"}))
                elif conns < self.config.get("rightsizeConnections", 5):
                    iclass = db.get("DBInstanceClass", "")
                    smaller = downsize_suggestion(iclass)
                    if smaller:
                        saving = round(rds_monthly(iclass, db.get("MultiAZ", False), region) - rds_monthly(smaller, db.get("MultiAZ", False), region), 2)
                        if saving > 0:
                            findings.append(Finding(dbid, dbid, "RDS", region,
                                                    f"Oversized — only {conns:.0f} avg connections over {self.cw_days}d on {iclass}. Downsize to {smaller} for same workload at lower hourly rate",
                                                    saving,
                                                    {"instance_class": iclass, "suggested_class": smaller,
                                                     "console_url": f"https://{region}.console.aws.amazon.com/rds/home?region={region}#database:id={dbid}"}))
        return findings


class DynamoDBScanner(BaseScanner):
    service = "DYNAMODB"

    def scan_region(self, region):
        findings = []
        ddb = get_client("dynamodb", region)
        for page in ddb.get_paginator("list_tables").paginate():
            for table in page.get("TableNames", []):
                rcu = get_sum(region, "AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", table, self.cw_days, self.cw_period)
                wcu = get_sum(region, "AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", table, self.cw_days, self.cw_period)
                if rcu < self.config.get("readCapacityUnits", 5) and wcu < self.config.get("writeCapacityUnits", 5):
                    findings.append(Finding(table, table, "DynamoDB", region,
                                            f"Near-zero usage over {self.cw_days}d (reads: {rcu:.0f}, writes: {wcu:.0f}) — provisioned capacity or on-demand minimum charges apply even with no traffic. Delete table or switch to on-demand if rarely used",
                                            25.0))
        return findings


class RedshiftScanner(BaseScanner):
    service = "REDSHIFT"

    def scan_region(self, region):
        findings = []
        rs = get_client("redshift", region)
        for page in rs.get_paginator("describe_clusters").paginate():
            for cluster in page.get("Clusters", []):
                cid = cluster["ClusterIdentifier"]
                conns = get_avg(region, "AWS/Redshift", "DatabaseConnections", "ClusterIdentifier", cid, self.cw_days, self.cw_period)
                if conns <= self.config.get("dbConnectionCount", 0):
                    ntype = cluster["NodeType"]
                    nodes = cluster["NumberOfNodes"]
                    monthly = redshift_monthly(ntype, nodes, region)
                    findings.append(Finding(cid, cid, "Redshift", region,
                                            f"Zero connections over {self.cw_days}d ({nodes}× {ntype}) — cluster is billed per-node per-hour even when idle. Pause, resize, or delete if unused",
                                            monthly,
                                            {"node_type": ntype, "nodes": nodes}))
        return findings


class ElastiCacheScanner(BaseScanner):
    service = "ELASTICACHE"

    def scan_region(self, region):
        findings = []
        ec = get_client("elasticache", region)
        for page in ec.get_paginator("describe_cache_clusters").paginate():
            for cache in page.get("CacheClusters", []):
                cid = cache["CacheClusterId"]
                hits = get_sum(region, "AWS/ElastiCache", "CacheHits", "CacheClusterId", cid, self.cw_days, self.cw_period)
                misses = get_sum(region, "AWS/ElastiCache", "CacheMisses", "CacheClusterId", cid, self.cw_days, self.cw_period)
                if hits + misses <= self.config.get("sumCacheHitMiss", 0):
                    ntype = cache.get("CacheNodeType", "cache.m5.large")
                    nnodes = cache.get("NumCacheNodes", 1)
                    monthly = elasticache_monthly(ntype, nnodes, region)
                    findings.append(Finding(cid, cid, "ElastiCache", region,
                                            f"Zero cache hits/misses over {self.cw_days}d ({nnodes}× {ntype}) — no application is using this cache but you're billed per-node per-hour. Delete if no longer needed",
                                            monthly))
        return findings


class DocumentDBScanner(BaseScanner):
    service = "DOCUMENTDB"

    def scan_region(self, region):
        findings = []
        docdb = get_client("docdb", region)
        for page in docdb.get_paginator("describe_db_clusters").paginate():
            for cluster in page.get("DBClusters", []):
                cid = cluster["DBClusterIdentifier"]
                conns = get_avg(region, "AWS/DocDB", "DatabaseConnections", "DBClusterIdentifier", cid, self.cw_days, self.cw_period)
                if conns == 0:
                    iclass = cluster.get("DBClusterMembers", [{}])[0].get("DBInstanceClass", "db.r5.large")
                    nmembers = len(cluster.get("DBClusterMembers", [1]))
                    monthly = documentdb_monthly(iclass, nmembers, region)
                    findings.append(Finding(cid, cid, "DocumentDB", region,
                                            f"Zero connections over {self.cw_days}d ({nmembers}× {iclass}) — cluster instances are billed hourly plus I/O and storage. Delete cluster if unused",
                                            monthly))
        return findings


class AuroraScanner(BaseScanner):
    service = "AURORA"

    def scan_region(self, region):
        findings = []
        rds = get_client("rds", region)
        for page in rds.get_paginator("describe_db_clusters").paginate():
            for cluster in page.get("DBClusters", []):
                if "aurora" not in cluster.get("Engine", ""):
                    continue
                cid = cluster["DBClusterIdentifier"]
                conns = get_avg(region, "AWS/RDS", "DatabaseConnections", "DBClusterIdentifier", cid, self.cw_days, self.cw_period)
                if conns == 0:
                    iclass = cluster.get("DBClusterMembers", [{}])[0].get("DBInstanceClass", "db.r5.large")
                    nmembers = len(cluster.get("DBClusterMembers", [1]))
                    monthly = aurora_monthly(iclass, nmembers, region)
                    findings.append(Finding(cid, cid, "Aurora", region,
                                            f"Zero connections over {self.cw_days}d ({nmembers}× {iclass}) — Aurora charges per-instance hourly plus I/O and storage. Delete or switch to Aurora Serverless v2 if usage is sporadic",
                                            monthly))
        return findings


class OpenSearchScanner(BaseScanner):
    service = "OPENSEARCH"

    def scan_region(self, region):
        findings = []
        os_client = get_client("opensearch", region)
        for domain in os_client.list_domain_names().get("DomainNames", []):
            name = domain["DomainName"]
            if get_avg(region, "AWS/ES", "SearchRate", "DomainName", name, self.cw_days, self.cw_period) == 0:
                try:
                    cfg = os_client.describe_domain(DomainName=name)["DomainStatus"]
                    itype = cfg.get("ClusterConfig", {}).get("InstanceType", "m5.large.search")
                    count = cfg.get("ClusterConfig", {}).get("InstanceCount", 1)
                    monthly = opensearch_monthly(itype, count, region)
                except Exception:
                    itype, count = "m5.large.search", 1
                    monthly = opensearch_monthly(itype, 1, region)
                findings.append(Finding(name, name, "OpenSearch", region,
                                        f"Zero search queries over {self.cw_days}d ({count}× {itype}) — domain instances are billed hourly plus EBS storage. Delete domain or reduce instance count if unused",
                                        monthly))
        return findings


class MSKScanner(BaseScanner):
    service = "MSK"

    def scan_region(self, region):
        findings = []
        msk = get_client("kafka", region)
        for page in msk.get_paginator("list_clusters").paginate():
            for cluster in page.get("ClusterInfoList", []):
                name = cluster["ClusterName"]
                bytes_in = get_sum(region, "AWS/Kafka", "BytesInPerSec", "Cluster Name", name, self.cw_days, self.cw_period)
                if bytes_in < self.config.get("min_bytes", 1000):
                    try:
                        info = msk.describe_cluster(ClusterArn=cluster["ClusterArn"])["ClusterInfo"]
                        itype = info.get("BrokerNodeGroupInfo", {}).get("InstanceType", "kafka.m5.large")
                        brokers = info.get("NumberOfBrokerNodes", 2)
                        monthly = msk_monthly(itype, brokers, region)
                    except Exception:
                        itype, brokers = "kafka.m5.large", 2
                        monthly = msk_monthly(itype, 2, region)
                    findings.append(Finding(name, name, "MSK", region,
                                            f"Near-zero throughput over {self.cw_days}d ({bytes_in:.0f} bytes in, {brokers}× {itype}) — brokers are billed per-hour regardless of traffic. Delete cluster if no longer producing/consuming",
                                            monthly))
        return findings


class ReservedInstanceScanner(BaseScanner):
    """Flag On-Demand EC2/RDS instances running >30d with no RI/SP coverage."""
    service = "RESERVED_INSTANCES"

    def scan_region(self, region):
        findings = []
        ec2 = get_client("ec2", region)
        min_days = self.config.get("min_days_running", 30)

        # Get active RIs
        active_ri_types = {
            ri["InstanceType"]
            for ri in ec2.describe_reserved_instances(
                Filters=[{"Name": "state", "Values": ["active"]}]
            ).get("ReservedInstances", [])
        }

        # Get active Savings Plans (us-east-1 is global endpoint)
        try:
            import boto3
            sp_client = boto3.client("savingsplans", region_name="us-east-1")
            has_sp = bool(sp_client.describe_savings_plans(
                filters=[{"name": "state", "values": ["active"]}]
            ).get("savingsPlans"))
        except Exception:
            has_sp = False

        if has_sp:
            return []  # Savings Plan covers all instance types

        from datetime import datetime, timezone
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        for page in ec2.get_paginator("describe_instances").paginate(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        ):
            for r in page["Reservations"]:
                for i in r["Instances"]:
                    itype = i.get("InstanceType", "")
                    if itype in active_ri_types:
                        continue
                    launch = i.get("LaunchTime")
                    if not launch:
                        continue
                    # boto3 returns timezone-aware datetime
                    from datetime import timezone
                    age_days = (datetime.now(timezone.utc) - launch).days
                    if age_days < min_days:
                        continue
                    name = next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), i["InstanceId"])
                    from kloudkut.core.pricing import ec2_monthly
                    monthly = ec2_monthly(itype, region)
                    # 1-year RI saves ~40% on average
                    saving = round(monthly * 0.40, 2)
                    findings.append(Finding(
                        i["InstanceId"], name, "Reserved Instances", region,
                        f"Running On-Demand for {age_days}d ({itype}) with no Reserved Instance or Savings Plan coverage — a 1-year RI would save ~40%. Consider purchasing RI or Compute Savings Plan",
                        saving,
                        {"instance_type": itype, "age_days": age_days,
                         "console_url": f"https://{region}.console.aws.amazon.com/ec2/v2/home?region={region}#ReservedInstances:"},
                        remediation=f"aws ec2 purchase-reserved-instances-offering --instance-type {itype} --region {region}"
                    ))
        return findings
