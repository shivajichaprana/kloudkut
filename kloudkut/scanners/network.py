"""Network scanners: EIP, ELB, NAT Gateway, CloudFront, API Gateway, VPC Endpoints, Route53."""
from kloudkut.core import BaseScanner, Finding, get_client, get_sum, nat_monthly
from kloudkut.core.pricing import EIP_MONTHLY


class EIPScanner(BaseScanner):
    service = "EIP"

    def scan_region(self, region):
        return [Finding(addr["AllocationId"], addr.get("PublicIp", ""), "EIP", region,
                        f"Elastic IP {addr.get('PublicIp', '')} not associated with any running instance — AWS charges $0.005/hr ($3.60/mo) for idle EIPs. Release if no longer needed",
                        EIP_MONTHLY,
                        remediation=f"aws ec2 release-address --allocation-id {addr['AllocationId']} --region {region}")
                for addr in get_client("ec2", region).describe_addresses().get("Addresses", [])
                if "AssociationId" not in addr]


class LoadBalancerScanner(BaseScanner):
    service = "LB"

    def scan_region(self, region):
        findings = []
        elb = get_client("elbv2", region)
        for page in elb.get_paginator("describe_load_balancers").paginate():
            for lb in page.get("LoadBalancers", []):
                name = lb["LoadBalancerName"]
                conns = get_sum(region, "AWS/ApplicationELB", "NewConnectionCount", "LoadBalancer",
                                lb["LoadBalancerArn"].split("loadbalancer/")[-1], self.cw_days, self.cw_period)
                if conns < self.config.get("connectionCount", 1):
                    findings.append(Finding(lb["LoadBalancerArn"], name, "LoadBalancer", region,
                                            f"Zero new connections over {self.cw_days}d — load balancer charges a fixed hourly fee (~$16/mo) plus LCU charges even with no traffic. Delete if backend services have been decommissioned",
                                            16.0))
        return findings


class NATGatewayScanner(BaseScanner):
    service = "NATGATEWAY"

    def scan_region(self, region):
        findings = []
        ec2 = get_client("ec2", region)
        for page in ec2.get_paginator("describe_nat_gateways").paginate(
            Filters=[{"Name": "state", "Values": ["available"]}]
        ):
            for nat in page.get("NatGateways", []):
                natid = nat["NatGatewayId"]
                bytes_out = get_sum(region, "AWS/NATGateway", "BytesOutToSource", "NatGatewayId", natid, self.cw_days, self.cw_period)
                if bytes_out < self.config.get("bytesOutToSource", 1000000):
                    findings.append(Finding(natid, natid, "NAT Gateway", region,
                                            f"Near-zero traffic over {self.cw_days}d ({bytes_out:.0f} bytes out) — NAT Gateway charges $0.045/hr ($32.85/mo) plus data processing fees even when idle. Delete if private subnets no longer need internet access",
                                            nat_monthly()))
        return findings


class CloudFrontScanner(BaseScanner):
    service = "CLOUDFRONT"

    def scan_region(self, region):
        findings = []
        cf = get_client("cloudfront", "us-east-1")
        for page in cf.get_paginator("list_distributions").paginate():
            for dist in page.get("DistributionList", {}).get("Items", []):
                did = dist["Id"]
                requests = get_sum("us-east-1", "AWS/CloudFront", "Requests", "DistributionId", did, self.cw_days, self.cw_period)
                if requests < self.config.get("min_requests", 100):
                    findings.append(Finding(did, dist["DomainName"], "CloudFront", "Global",
                                            f"Only {requests:.0f} requests over {self.cw_days}d — distribution has near-zero traffic but still incurs minimum monthly charges. Disable or delete if the origin is no longer serving content",
                                            10.0))
        return findings


class APIGatewayScanner(BaseScanner):
    service = "APIGATEWAY"

    def scan_region(self, region):
        findings = []
        apigw = get_client("apigateway", region)
        for page in apigw.get_paginator("get_rest_apis").paginate():
            for api in page.get("items", []):
                name = api["name"]
                count = get_sum(region, "AWS/ApiGateway", "Count", "ApiName", name, self.cw_days, self.cw_period)
                if count < self.config.get("min_requests", 10):
                    findings.append(Finding(api["id"], name, "API Gateway", region,
                                            f"Only {count:.0f} API calls over {self.cw_days}d — REST API exists but receives almost no traffic. Delete if the backend has been decommissioned",
                                            3.5))
        return findings


class VPCEndpointScanner(BaseScanner):
    service = "VPC_ENDPOINTS"

    def scan_region(self, region):
        findings = []
        ec2 = get_client("ec2", region)
        for page in ec2.get_paginator("describe_vpc_endpoints").paginate():
            for ep in page.get("VpcEndpoints", []):
                epid = ep["VpcEndpointId"]
                processed = get_sum(region, "AWS/PrivateLinkEndpoints", "BytesProcessed",
                                    "VPC Endpoint Id", epid, self.cw_days, self.cw_period)
                if processed == 0:
                    findings.append(Finding(epid, ep["ServiceName"], "VPC Endpoint", region,
                                            f"Zero bytes processed over {self.cw_days}d — Interface VPC Endpoints charge ~$7.50/mo per AZ plus data processing fees even with no traffic. Delete if the connected service is no longer used from this VPC",
                                            7.5))
        return findings


class Route53Scanner(BaseScanner):
    service = "ROUTE53"

    def scan_region(self, region):
        findings = []
        r53 = get_client("route53", "us-east-1")
        for page in r53.get_paginator("list_hosted_zones").paginate():
            for zone in page.get("HostedZones", []):
                zid = zone["Id"].split("/")[-1]
                queries = get_sum("us-east-1", "AWS/Route53", "QueryCount", "HostedZoneId", zid, self.cw_days, self.cw_period)
                if queries == 0:
                    findings.append(Finding(zid, zone["Name"], "Route53", "Global",
                                            f"Zero DNS queries over {self.cw_days}d — hosted zone charges $0.50/mo regardless of traffic. Delete if domain is no longer in use or DNS has been migrated elsewhere",
                                            0.5))
        return findings
