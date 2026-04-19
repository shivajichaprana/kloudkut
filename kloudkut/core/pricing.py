"""AWS instance pricing lookup (on-demand, us-east-1 base, Linux).

All base prices are us-east-1 On-Demand, verified against AWS official pricing
pages (April 2026).  Region-varying services are adjusted via region_multiplier().

Global flat-rate services (same in all regions):
  KMS ($1/mo/key), Secrets Manager ($0.40/mo), WAF ($5/mo/ACL),
  Route53 ($0.50/mo/zone), CloudWatch Alarms ($0.10/mo), ECR ($0.10/GB/mo),
  EKS cluster ($0.10/hr), EIP ($0.005/hr).
"""

# ── EC2 hourly on-demand prices (us-east-1, Linux) ──
EC2_HOURLY: dict[str, float] = {
    "t2.nano": 0.0058, "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
    "t2.large": 0.0928, "t2.xlarge": 0.1856, "t2.2xlarge": 0.3712,
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
    "t3.large": 0.0832, "t3.xlarge": 0.1664, "t3.2xlarge": 0.3328,
    "t3a.nano": 0.0047, "t3a.micro": 0.0094, "t3a.small": 0.0188, "t3a.medium": 0.0376,
    "t3a.large": 0.0752, "t3a.xlarge": 0.1504, "t3a.2xlarge": 0.3008,
    "t4g.nano": 0.0042, "t4g.micro": 0.0084, "t4g.small": 0.0168, "t4g.medium": 0.0336,
    "t4g.large": 0.0672, "t4g.xlarge": 0.1344, "t4g.2xlarge": 0.2688,
    "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
    "m5.8xlarge": 1.536, "m5.12xlarge": 2.304, "m5.16xlarge": 3.072, "m5.24xlarge": 4.608,
    "m6i.large": 0.096, "m6i.xlarge": 0.192, "m6i.2xlarge": 0.384, "m6i.4xlarge": 0.768,
    "m6i.8xlarge": 1.536, "m6i.12xlarge": 2.304, "m6i.16xlarge": 3.072, "m6i.24xlarge": 4.608,
    "m6g.large": 0.077, "m6g.xlarge": 0.154, "m6g.2xlarge": 0.308, "m6g.4xlarge": 0.616,
    "c5.large": 0.085, "c5.xlarge": 0.17, "c5.2xlarge": 0.34, "c5.4xlarge": 0.68,
    "c5.9xlarge": 1.53, "c5.12xlarge": 2.04, "c5.18xlarge": 3.06, "c5.24xlarge": 4.08,
    "c6i.large": 0.085, "c6i.xlarge": 0.17, "c6i.2xlarge": 0.34, "c6i.4xlarge": 0.68,
    "c6g.large": 0.068, "c6g.xlarge": 0.136, "c6g.2xlarge": 0.272, "c6g.4xlarge": 0.544,
    "r5.large": 0.126, "r5.xlarge": 0.252, "r5.2xlarge": 0.504, "r5.4xlarge": 1.008,
    "r5.8xlarge": 2.016, "r5.12xlarge": 3.024, "r5.16xlarge": 4.032, "r5.24xlarge": 6.048,
    "r6i.large": 0.126, "r6i.xlarge": 0.252, "r6i.2xlarge": 0.504, "r6i.4xlarge": 1.008,
    "r6g.large": 0.1008, "r6g.xlarge": 0.2016, "r6g.2xlarge": 0.4032, "r6g.4xlarge": 0.8064,
    "p3.2xlarge": 3.06, "p3.8xlarge": 12.24, "p3.16xlarge": 24.48,
    "p4d.24xlarge": 32.77,
    "g4dn.xlarge": 0.526, "g4dn.2xlarge": 0.752, "g4dn.4xlarge": 1.204,
    "g4dn.8xlarge": 2.264, "g4dn.12xlarge": 3.912, "g4dn.16xlarge": 4.528,
    "x1e.xlarge": 3.336, "x1e.2xlarge": 6.672, "x1e.4xlarge": 13.344,
}

# ── RDS hourly on-demand prices (us-east-1, MySQL/PostgreSQL Single-AZ) ──
RDS_HOURLY: dict[str, float] = {
    "db.t3.micro": 0.017, "db.t3.small": 0.034, "db.t3.medium": 0.068,
    "db.t3.large": 0.136, "db.t3.xlarge": 0.272, "db.t3.2xlarge": 0.544,
    "db.t4g.micro": 0.016, "db.t4g.small": 0.032, "db.t4g.medium": 0.065,
    "db.t4g.large": 0.13, "db.t4g.xlarge": 0.26, "db.t4g.2xlarge": 0.52,
    "db.m5.large": 0.171, "db.m5.xlarge": 0.342, "db.m5.2xlarge": 0.684,
    "db.m5.4xlarge": 1.368, "db.m5.8xlarge": 2.736, "db.m5.12xlarge": 4.104,
    "db.m6g.large": 0.153, "db.m6g.xlarge": 0.306, "db.m6g.2xlarge": 0.612,
    "db.m6g.4xlarge": 1.224, "db.m6g.8xlarge": 2.448, "db.m6g.12xlarge": 3.672,
    "db.r5.large": 0.24, "db.r5.xlarge": 0.48, "db.r5.2xlarge": 0.96,
    "db.r5.4xlarge": 1.92, "db.r5.8xlarge": 3.84, "db.r5.12xlarge": 5.76,
    "db.r6g.large": 0.192, "db.r6g.xlarge": 0.384, "db.r6g.2xlarge": 0.768,
    "db.r6g.4xlarge": 1.536, "db.r6g.8xlarge": 3.072, "db.r6g.12xlarge": 4.608,
}

# ── Redshift node hourly prices (us-east-1) ──
REDSHIFT_HOURLY: dict[str, float] = {
    "dc2.large": 0.25, "dc2.8xlarge": 4.80,
    "ra3.xlplus": 1.086, "ra3.4xlarge": 3.26, "ra3.16xlarge": 13.04,
    "ds2.xlarge": 0.85, "ds2.8xlarge": 6.80,
}

# ── ElastiCache node hourly prices (us-east-1, Redis OSS) ──
ELASTICACHE_HOURLY: dict[str, float] = {
    "cache.t3.micro": 0.017, "cache.t3.small": 0.034, "cache.t3.medium": 0.068,
    "cache.t4g.micro": 0.016, "cache.t4g.small": 0.032, "cache.t4g.medium": 0.065,
    "cache.m5.large": 0.124, "cache.m5.xlarge": 0.248, "cache.m5.2xlarge": 0.497,
    "cache.m6g.large": 0.113, "cache.m6g.xlarge": 0.226, "cache.m6g.2xlarge": 0.452,
    "cache.r5.large": 0.216, "cache.r5.xlarge": 0.432, "cache.r5.2xlarge": 0.864,
    "cache.r6g.large": 0.149, "cache.r6g.xlarge": 0.298, "cache.r6g.2xlarge": 0.597,
}

# ── SageMaker endpoint instance hourly prices (us-east-1) ──
SAGEMAKER_HOURLY: dict[str, float] = {
    "ml.t2.medium": 0.065, "ml.t2.large": 0.13, "ml.t2.xlarge": 0.26,
    "ml.m4.xlarge": 0.28, "ml.m4.2xlarge": 0.56, "ml.m4.4xlarge": 1.12,
    "ml.m5.large": 0.134, "ml.m5.xlarge": 0.269, "ml.m5.2xlarge": 0.538,
    "ml.c5.large": 0.119, "ml.c5.xlarge": 0.238, "ml.c5.2xlarge": 0.476,
    "ml.p2.xlarge": 1.361, "ml.p3.2xlarge": 4.284,
    "ml.g4dn.xlarge": 0.736, "ml.g4dn.2xlarge": 1.052,
}

# ── OpenSearch instance hourly prices (us-east-1) ──
OPENSEARCH_HOURLY: dict[str, float] = {
    "t3.small.search": 0.036, "t3.medium.search": 0.073,
    "m5.large.search": 0.142, "m5.xlarge.search": 0.284, "m5.2xlarge.search": 0.568,
    "m6g.large.search": 0.128, "m6g.xlarge.search": 0.256, "m6g.2xlarge.search": 0.512,
    "r5.large.search": 0.187, "r5.xlarge.search": 0.374, "r5.2xlarge.search": 0.748,
    "r6g.large.search": 0.167, "r6g.xlarge.search": 0.335, "r6g.2xlarge.search": 0.670,
    "c5.large.search": 0.118, "c5.xlarge.search": 0.235, "c5.2xlarge.search": 0.470,
}

# ── MSK broker hourly prices (us-east-1) ──
MSK_HOURLY: dict[str, float] = {
    "kafka.t3.small": 0.054,
    "kafka.m5.large": 0.216, "kafka.m5.xlarge": 0.432, "kafka.m5.2xlarge": 0.864,
    "kafka.m5.4xlarge": 1.728, "kafka.m5.8xlarge": 3.456, "kafka.m5.12xlarge": 5.184,
}

# ── DocumentDB instance hourly prices (us-east-1) ──
DOCUMENTDB_HOURLY: dict[str, float] = {
    "db.t3.medium": 0.076,
    "db.r5.large": 0.277, "db.r5.xlarge": 0.554, "db.r5.2xlarge": 1.109,
    "db.r5.4xlarge": 2.218, "db.r5.8xlarge": 4.435, "db.r5.12xlarge": 6.653,
    "db.r6g.large": 0.250, "db.r6g.xlarge": 0.499, "db.r6g.2xlarge": 0.998,
}

# ── Aurora instance hourly prices (us-east-1, MySQL-compatible) ──
AURORA_HOURLY: dict[str, float] = {
    "db.t3.small": 0.041, "db.t3.medium": 0.082,
    "db.t4g.medium": 0.073, "db.t4g.large": 0.146,
    "db.r5.large": 0.285, "db.r5.xlarge": 0.570, "db.r5.2xlarge": 1.140,
    "db.r5.4xlarge": 2.280, "db.r5.8xlarge": 4.560, "db.r5.12xlarge": 6.840,
    "db.r6g.large": 0.256, "db.r6g.xlarge": 0.513, "db.r6g.2xlarge": 1.026,
}

# ── Global flat-rate pricing (same in all regions) ──
EKS_CLUSTER_HOURLY = 0.10   # $0.10/hr per cluster — global
EIP_HOURLY = 0.005           # $0.005/hr — global (all EIPs since Feb 2024)
EIP_MONTHLY = 3.65           # $0.005/hr × 730

# ── NAT Gateway hourly per region ──
_NAT_HOURLY: dict[str, float] = {
    "us-east-1": 0.045, "us-east-2": 0.045, "us-west-1": 0.045, "us-west-2": 0.045,
    "ca-central-1": 0.045,
    "eu-west-1": 0.048, "eu-west-2": 0.048, "eu-west-3": 0.048,
    "eu-central-1": 0.048, "eu-north-1": 0.048, "eu-south-1": 0.048,
    "ap-south-1": 0.045, "ap-southeast-1": 0.048, "ap-southeast-2": 0.048,
    "ap-northeast-1": 0.048, "ap-northeast-2": 0.048, "ap-northeast-3": 0.048,
    "sa-east-1": 0.065,
    "me-south-1": 0.048, "af-south-1": 0.048,
}

# ── EBS per-GB/mo prices (us-east-1) — region-adjusted via multiplier ──
EBS_GB_MONTHLY: dict[str, float] = {
    "gp2": 0.10, "gp3": 0.08, "io1": 0.125, "io2": 0.125,
    "st1": 0.045, "sc1": 0.015, "standard": 0.05,
}

# ── Storage per-GB/mo prices (us-east-1) — region-adjusted via multiplier ──
EFS_GB_MONTHLY = 0.30        # standard storage class
CW_LOGS_GB_MONTHLY = 0.03   # CloudWatch Logs storage
ECR_GB_MONTHLY = 0.10        # ECR — global flat rate (not region-adjusted)


# ── Region price multipliers (relative to us-east-1) ──
# Derived from EC2 t3/m5/r5 price ratios across regions.  Applied to all
# region-varying services: EC2, RDS, ElastiCache, Redshift, OpenSearch,
# MSK, SageMaker, Aurora, DocumentDB, EBS, EFS, CloudWatch Logs.
_REGION_MULTIPLIER: dict[str, float] = {
    "us-east-1": 1.00, "us-east-2": 1.00, "us-west-1": 1.16, "us-west-2": 1.00,
    "ca-central-1": 1.10,
    "eu-west-1": 1.10, "eu-west-2": 1.16, "eu-west-3": 1.17,
    "eu-central-1": 1.15, "eu-north-1": 1.12, "eu-south-1": 1.15,
    "ap-south-1": 0.92,
    "ap-southeast-1": 1.15, "ap-southeast-2": 1.16,
    "ap-northeast-1": 1.30, "ap-northeast-2": 1.15, "ap-northeast-3": 1.30,
    "sa-east-1": 1.45,
    "me-south-1": 1.18, "af-south-1": 1.29,
}


def region_multiplier(region: str) -> float:
    return _REGION_MULTIPLIER.get(region, 1.10)


# ── Monthly cost functions (all region-aware) ──

def ec2_monthly(instance_type: str, region: str = "us-east-1") -> float:
    return round(EC2_HOURLY.get(instance_type, 0.10) * 730 * region_multiplier(region), 2)


def rds_monthly(instance_class: str, multi_az: bool = False, region: str = "us-east-1") -> float:
    hourly = RDS_HOURLY.get(instance_class, 0.17)
    return round(hourly * (2 if multi_az else 1) * 730 * region_multiplier(region), 2)


def redshift_monthly(node_type: str, node_count: int = 1, region: str = "us-east-1") -> float:
    return round(REDSHIFT_HOURLY.get(node_type, 1.0) * 730 * node_count * region_multiplier(region), 2)


def elasticache_monthly(node_type: str, num_nodes: int = 1, region: str = "us-east-1") -> float:
    return round(ELASTICACHE_HOURLY.get(node_type, 0.124) * 730 * num_nodes * region_multiplier(region), 2)


def sagemaker_monthly(instance_type: str, region: str = "us-east-1") -> float:
    return round(SAGEMAKER_HOURLY.get(instance_type, 0.269) * 730 * region_multiplier(region), 2)


def opensearch_monthly(instance_type: str, instance_count: int = 1, region: str = "us-east-1") -> float:
    return round(OPENSEARCH_HOURLY.get(instance_type, 0.142) * 730 * instance_count * region_multiplier(region), 2)


def msk_monthly(instance_type: str, broker_count: int = 2, region: str = "us-east-1") -> float:
    return round(MSK_HOURLY.get(instance_type, 0.216) * 730 * broker_count * region_multiplier(region), 2)


def eks_monthly() -> float:
    """EKS cluster fee — global flat rate, no region adjustment."""
    return round(EKS_CLUSTER_HOURLY * 730, 2)


def nat_monthly(region: str = "us-east-1") -> float:
    """NAT Gateway — uses per-region hourly rates."""
    return round(_NAT_HOURLY.get(region, 0.045) * 730, 2)


def documentdb_monthly(instance_class: str, instance_count: int = 1, region: str = "us-east-1") -> float:
    return round(DOCUMENTDB_HOURLY.get(instance_class, 0.277) * 730 * instance_count * region_multiplier(region), 2)


def aurora_monthly(instance_class: str, instance_count: int = 1, region: str = "us-east-1") -> float:
    return round(AURORA_HOURLY.get(instance_class, 0.285) * 730 * instance_count * region_multiplier(region), 2)


def ebs_monthly(size_gb: int, volume_type: str = "gp2", region: str = "us-east-1") -> float:
    """EBS volume — price varies by type and region."""
    gb_price = EBS_GB_MONTHLY.get(volume_type, 0.10)
    return round(size_gb * gb_price * region_multiplier(region), 2)


def efs_monthly(size_gb: float, region: str = "us-east-1") -> float:
    return round(size_gb * EFS_GB_MONTHLY * region_multiplier(region), 2)


def cw_logs_monthly(size_mb: float, region: str = "us-east-1") -> float:
    """CloudWatch Logs storage cost from MB stored."""
    size_gb = size_mb / 1024
    return round(size_gb * CW_LOGS_GB_MONTHLY * region_multiplier(region), 2)


# ── Right-sizing: next smaller instance in same family ──
_DOWNSIZE: dict[str, str] = {
    "t3.xlarge": "t3.large", "t3.2xlarge": "t3.xlarge",
    "t3a.xlarge": "t3a.large", "t3a.2xlarge": "t3a.xlarge",
    "m5.xlarge": "m5.large", "m5.2xlarge": "m5.xlarge", "m5.4xlarge": "m5.2xlarge",
    "m5.8xlarge": "m5.4xlarge", "m5.12xlarge": "m5.8xlarge",
    "m6i.xlarge": "m6i.large", "m6i.2xlarge": "m6i.xlarge", "m6i.4xlarge": "m6i.2xlarge",
    "c5.xlarge": "c5.large", "c5.2xlarge": "c5.xlarge", "c5.4xlarge": "c5.2xlarge",
    "c6i.xlarge": "c6i.large", "c6i.2xlarge": "c6i.xlarge",
    "r5.xlarge": "r5.large", "r5.2xlarge": "r5.xlarge", "r5.4xlarge": "r5.2xlarge",
    "r6i.xlarge": "r6i.large", "r6i.2xlarge": "r6i.xlarge",
    "db.t3.xlarge": "db.t3.large", "db.t3.2xlarge": "db.t3.xlarge",
    "db.m5.xlarge": "db.m5.large", "db.m5.2xlarge": "db.m5.xlarge", "db.m5.4xlarge": "db.m5.2xlarge",
    "db.r5.xlarge": "db.r5.large", "db.r5.2xlarge": "db.r5.xlarge", "db.r5.4xlarge": "db.r5.2xlarge",
}


def downsize_suggestion(instance_type: str) -> str | None:
    return _DOWNSIZE.get(instance_type)
