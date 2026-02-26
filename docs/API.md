# KloudKut API Documentation

## Python API

### Basic Usage

```python
from kloudkut import BaseScanner, Finding, load_config, get_regions
from kloudkut.scanners import EC2Scanner, RDSScanner

# Load configuration
config = load_config()

# Get all AWS regions
regions = get_regions()

# Scan EC2 instances
ec2_scanner = EC2Scanner(config, regions)
findings = ec2_scanner.scan(use_cache=True)

# Process findings
for finding in findings:
    print(f"{finding.service}: {finding.resource_name} - ${finding.monthly_cost}/mo")
```

### Custom Scanner

```python
from kloudkut import BaseScanner, Finding

class CustomScanner(BaseScanner):
    service = "CUSTOM"
    
    def scan_region(self, region: str) -> list[Finding]:
        client = get_client("ec2", region)
        return [
            Finding(
                resource_id="resource-123",
                resource_name="my-resource",
                service=self.service,
                region=region,
                reason="Idle for 30 days",
                monthly_cost=100.0,
                details={"cpu": 0.5},
                remediation="aws ec2 stop-instances --instance-ids resource-123"
            )
        ]
```

## CLI Reference

```bash
# Full scan
kloudkut

# Specific services
kloudkut --services EC2 RDS S3

# Multi-account scan
kloudkut --accounts 123456789012 987654321098 --role-name OrganizationAccountAccessRole

# Export reports
kloudkut --json findings.json --csv --html report.html

# CI/CD mode
kloudkut --min-cost 50 --fail-on-findings
```
