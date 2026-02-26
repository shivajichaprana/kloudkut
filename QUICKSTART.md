# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Install

```bash
pip install kloudkut
```

### Step 2: Configure AWS

```bash
aws configure
# Enter your AWS credentials
```

### Step 3: Run Your First Scan

```bash
kloudkut
```

That's it! You'll see a report of idle resources and potential savings.

## 📊 View Results

### Terminal Output
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎯 KloudKut v5.0.0 — AWS Cost Optimization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanning EC2                    ████████████████████ 100%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCAN COMPLETE  (45.2s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Idle Resources:  25
  Services Hit:    8
  Monthly Savings: $4,730.00
  Annual Savings:  $56,760.00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Generate Reports

```bash
# HTML report
kloudkut --html report.html

# JSON export
kloudkut --json findings.json

# CSV export
kloudkut --csv
```

### Web Dashboard

```bash
python dashboard.py
# Open http://localhost:5000
```

## 🎯 Common Use Cases

### 1. Scan Specific Services

```bash
kloudkut --services EC2 RDS S3
```

### 2. Scan Specific Regions

```bash
kloudkut --regions us-east-1 eu-west-1
```

### 3. Filter by Cost

```bash
# Only show resources costing > $100/month
kloudkut --min-cost 100
```

### 4. Exclude Production

```bash
kloudkut --exclude-tag Environment=production
```

### 5. Multi-Account Scan

```bash
kloudkut --accounts 111111111111 222222222222 \
         --role-name OrganizationAccountAccessRole
```

### 6. CI/CD Integration

```bash
# Exit with code 1 if findings found
kloudkut --min-cost 50 --fail-on-findings
```

## 🔔 Set Up Notifications

Edit `config/config.yaml`:

```yaml
notifications:
  slack:
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  
  email:
    from_address: kloudkut@example.com
    to_address: team@example.com
    ses_region: us-east-1
```

Then run:

```bash
kloudkut --notify
```

## 🐳 Docker

```bash
docker run --rm \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  kloudkut/kloudkut:latest
```

## 🔧 Customize Thresholds

Edit `config/config.yaml`:

```yaml
resources:
  EC2:
    avgCpu: 5          # CPU threshold %
    netInOut: 10000    # Network bytes
  
  RDS:
    connectionCount: 0  # Min connections
  
  S3:
    daysInactive: 90   # Days without access
```

## 📈 Monitor Performance

```python
from kloudkut import get_summary

summary = get_summary()
print(f"Scanned {summary['services_scanned']} services")
print(f"Found {summary['total_findings']} issues")
```

## 🆘 Troubleshooting

### No credentials found
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=yyy
```

### Permission denied
Ensure your IAM user/role has `ReadOnlyAccess` or required permissions.

### Slow scans
```bash
# Scan fewer regions
kloudkut --regions us-east-1

# Use cache
kloudkut  # Cache enabled by default

# Scan specific services
kloudkut --services EC2 RDS
```

## 📚 Learn More

- [Full Documentation](README.md)
- [API Reference](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Examples](examples/)

## 💡 Pro Tips

1. **Use caching**: First scan takes 2-5 min, subsequent scans use cache (1-hour TTL)
2. **Start small**: Scan 1-2 services first to understand output
3. **Set thresholds**: Customize in `config/config.yaml` for your needs
4. **Automate**: Run weekly via cron/Lambda for continuous monitoring
5. **Multi-account**: Use Organizations + AssumeRole for centralized scanning

## 🎓 Next Steps

1. ✅ Run your first scan
2. ✅ Generate HTML report
3. ✅ Set up notifications
4. ✅ Customize thresholds
5. ✅ Automate with CI/CD

Happy cost optimizing! 🎯
