# KloudKut 🎯

> AWS Cost Optimization — identify idle resources and save $3,000–$34,000/month.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![45 Services](https://img.shields.io/badge/services-45-green.svg)](#supported-services)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Installation

### From Source

```bash
# Clone repository
git clone https://github.com/shivajichaprana/kloudkut.git
cd KloudKut

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Development Mode

```bash
# Install in editable mode
pip install -e .

# Run from anywhere
kloudkut --help
```

## Quick Start

```bash
# Check Python version
python3 --version  # Requires 3.12+

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure  # Or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# Run scan
python main.py
```

## Usage

```bash
# Full scan
python main.py

# Specific services
python main.py --services EC2 RDS S3

# Specific regions
python main.py --regions us-east-1 eu-west-1

# Export reports
python main.py --json findings.json --csv --html report.html

# Exclude production resources by tag
python main.py --exclude-tag Environment=production DoNotDelete=true

# Only show findings above cost threshold
python main.py --min-cost 100

# Send Slack/email notifications (configure in config/config.yaml)
python main.py --notify

# CI/CD — exit code 1 if findings found above threshold
python main.py --min-cost 50 --fail-on-findings

# Web dashboard
python dashboard.py          # → http://localhost:5000
# ⚠️  WARNING: Dashboard has no authentication. Use only on trusted networks or localhost.

# Docker
docker build -t kloudkut .
docker run --rm -e AWS_ACCESS_KEY_ID=<key> -e AWS_SECRET_ACCESS_KEY=<secret> kloudkut

# Utilities
python main.py --version     # Show version
python main.py --dry-run     # Preview what would be scanned
python main.py --clear-cache # Clear cached results
python main.py --verbose     # Debug logging
```

## Project Structure

```
KloudKut/
├── kloudkut/
│   ├── core/
│   │   ├── aws.py        # AWS client factory (cached)
│   │   ├── metrics.py    # CloudWatch helpers
│   │   ├── scanner.py    # BaseScanner (parallel + cached)
│   │   └── config.py     # Config loader
│   ├── scanners/
│   │   ├── compute.py    # EC2, Lambda, ECS, EKS, EMR, Glue…
│   │   ├── database.py   # RDS, DynamoDB, Redshift, Aurora…
│   │   ├── storage.py    # S3, EBS, EFS, FSx, Backup…
│   │   ├── network.py    # ELB, NAT, CloudFront, API GW…
│   │   ├── security.py   # GuardDuty, WAF, KMS, Macie…
│   │   └── analytics.py  # Kinesis, SQS, SNS, Athena…
│   └── reports/          # HTML, CSV, JSON generators
├── config/
│   ├── default.yaml      # Default thresholds
│   └── config.yaml       # Your overrides
├── tests/
├── main.py
├── dashboard.py
└── requirements.txt
```

## Supported Services (45)

| Category | Services |
|----------|----------|
| **Compute** | EC2, Lambda, ECS, EKS, EMR, Glue, Lightsail, CodeBuild |
| **Database** | RDS, DynamoDB, Redshift, ElastiCache, DocumentDB, Aurora, OpenSearch, MSK |
| **Storage** | S3, EBS, EFS, FSx, Backup, ECR |
| **Network** | ELB, NAT Gateway, CloudFront, API Gateway, EIP, VPC Endpoints, Route53 |
| **Security** | GuardDuty, WAF, KMS, Secrets Manager, Macie, Security Hub |
| **Analytics** | Kinesis, SQS, SNS, Step Functions, SageMaker, Athena |
| **Management** | CloudFormation, EventBridge, CloudWatch Alarms, CloudWatch Logs |

## Configuration

Edit `config/config.yaml` to override thresholds:

```yaml
resources:
  EC2:
    avgCpu: 5      # Flag instances with avg CPU < 5%
  RDS:
    connectionCount: 0
```

## Requirements

- Python 3.12+
- AWS credentials configured (`aws configure` or env vars)
- IAM Permissions (minimum required):
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "ec2:Describe*",
          "rds:Describe*",
          "s3:List*",
          "s3:GetBucketLocation",
          "lambda:List*",
          "dynamodb:Describe*",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "elasticloadbalancing:Describe*",
          "ecs:Describe*",
          "eks:Describe*",
          "elasticache:Describe*",
          "redshift:Describe*",
          "kinesis:Describe*",
          "sqs:List*",
          "sns:List*",
          "kms:List*",
          "guardduty:List*",
          "wafv2:List*",
          "apigateway:GET",
          "cloudfront:List*",
          "route53:List*",
          "backup:List*",
          "fsx:Describe*",
          "efs:Describe*",
          "glue:Get*",
          "emr:List*",
          "sagemaker:List*",
          "athena:List*",
          "stepfunctions:List*",
          "secretsmanager:List*",
          "macie2:List*",
          "securityhub:Get*",
          "logs:Describe*",
          "events:List*",
          "cloudformation:Describe*"
        ],
        "Resource": "*"
      }
    ]
  }
  ```
  Or use AWS managed policy: `ReadOnlyAccess`

## License

MIT — see [LICENSE](LICENSE)


## Documentation

- [Changelog](CHANGELOG.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)

## Cost Savings Examples

Real-world savings from KloudKut scans:

- **Idle EC2 instances**: $2,400/month (10 t3.large instances at $0.0832/hr)
- **Unattached EBS volumes**: $500/month (5TB at $0.10/GB-month)
- **Unused NAT Gateways**: $1,080/month (3 gateways at $0.045/hr)
- **Old RDS snapshots**: $300/month (3TB at $0.095/GB-month)
- **Idle Load Balancers**: $450/month (20 ALBs at $0.0225/hr)

**Total potential savings: $4,730/month or $56,760/year**

## Rate Limiting

KloudKut respects AWS API rate limits:
- Parallel execution: 10 workers per service
- Built-in retry logic: 3 attempts with adaptive backoff
- CloudWatch metrics: Batched queries with 14-day windows
- Caching: 1-hour TTL to reduce repeated API calls

To minimize API calls:
```bash
# Scan specific regions only
python main.py --regions us-east-1

# Scan specific services
python main.py --services EC2 RDS S3

# Use cached results
python main.py  # Default behavior
```
