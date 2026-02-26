#!/usr/bin/env python3
"""Example: Custom scanner for detecting idle resources."""
from kloudkut import BaseScanner, Finding, get_client

class CustomIdleScanner(BaseScanner):
    service = "CUSTOM"
    
    def scan_region(self, region: str) -> list[Finding]:
        findings = []
        ec2 = get_client("ec2", region)
        
        try:
            response = ec2.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )
            
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                    
                    if tags.get("AutoShutdown") == "true":
                        findings.append(Finding(
                            resource_id=instance_id,
                            resource_name=tags.get("Name", instance_id),
                            service=self.service,
                            region=region,
                            reason="Tagged for auto-shutdown",
                            monthly_cost=50.0,
                            remediation=f"aws ec2 stop-instances --instance-ids {instance_id}"
                        ))
        except Exception as e:
            print(f"Error: {e}")
        
        return findings

if __name__ == "__main__":
    from kloudkut import load_config
    scanner = CustomIdleScanner(load_config(), ["us-east-1"])
    findings = scanner.scan(use_cache=False)
    print(f"Found {len(findings)} resources")
