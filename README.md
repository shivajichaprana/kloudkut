# KloudKut 🎯

> Enterprise-grade AWS Cost Optimization — Identify idle resources and save $3,000–$34,000/month

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## 🚀 Quick Start

```bash
pip install kloudkut
kloudkut
```

## ✨ Features

- **45+ AWS Services** - EC2, RDS, S3, Lambda, ECS, EKS, and more
- **Multi-Account** - Scan across AWS Organizations
- **Parallel Scanning** - Fast execution with concurrent regions
- **Smart Caching** - 1-hour TTL reduces API calls by 90%
- **Rich Reports** - HTML, CSV, JSON, SARIF, JUnit
- **Notifications** - Slack, Email (SES)
- **Web Dashboard** - Real-time monitoring
- **CI/CD Ready** - GitHub Actions, Jenkins, GitLab
- **Docker & Lambda** - Multiple deployment options
- **Remediation** - Auto-generated AWS CLI commands

## 📊 Example Output

```bash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎯 KloudKut v5.0.0 — AWS Cost Optimization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Idle Resources:  25
  Monthly Savings: $4,730.00
  Annual Savings:  $56,760.00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🎯 Use Cases

```bash
# Scan specific services
kloudkut --services EC2 RDS S3

# Multi-account scan
kloudkut --accounts 111111111111 222222222222

# Export reports
kloudkut --json findings.json --html report.html

# CI/CD mode
kloudkut --min-cost 100 --fail-on-findings
```

## Architecture

```
┌──────────────┐     ┌───────────────────────────────────────────┐
│  CLI / CI/CD │────▶│              KloudKut Engine               │
│  Interface   │     │                                           │
└──────────────┘     │  ┌─────────────┐  ┌────────────────────┐  │
                     │  │ Service     │  │ Smart Cache        │  │
                     │  │ Scanner     │  │ (1h TTL, 90% less  │  │
                     │  │ (45+ AWS)   │  │  API calls)        │  │
                     │  └──────┬──────┘  └────────────────────┘  │
                     │         │                                  │
                     │         ▼                                  │
                     │  ┌─────────────────────────────────────┐  │
                     │  │      Parallel Region Scanner        │  │
                     │  │  (concurrent multi-region + account)│  │
                     │  └──────┬──────────────────────────────┘  │
                     │         │                                  │
                     │         ▼                                  │
                     │  ┌─────────────┐  ┌────────────────────┐  │
                     │  │ Cost        │  │ Report Generator   │  │
                     │  │ Analyzer    │  │ (HTML/CSV/JSON/    │  │
                     │  │             │  │  SARIF/JUnit)      │  │
                     │  └─────────────┘  └────────────────────┘  │
                     └───────────────────────────────────────────┘
                               │
                     ┌─────────┼─────────┐
                     ▼         ▼         ▼
              ┌──────────┐ ┌───────┐ ┌──────────┐
              │  Slack   │ │  SES  │ │ Web      │
              │ Alerts   │ │ Email │ │ Dashboard│
              └──────────┘ └───────┘ └──────────┘
```

## Project Structure

```
kloudkut/
├── kloudkut/              # Core package
│   ├── __init__.py
│   ├── scanner.py         # Service scanners (45+ AWS services)
│   ├── cache.py           # Smart caching layer
│   ├── reporter.py        # Multi-format report generation
│   └── notifier.py        # Slack/SES notifications
├── tests/                 # Unit tests
├── config/                # Configuration templates
├── examples/              # Usage examples
├── docs/                  # API & architecture docs
├── .github/workflows/     # CI pipeline
├── Dockerfile             # Container deployment
├── docker-compose.yml     # Dashboard setup
├── Makefile               # Dev shortcuts
└── pyproject.toml         # Package config
```

## 📚 Documentation

- [Quick Start](QUICKSTART.md)
- [API Documentation](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)

## 💰 Cost Savings

| Resource | Monthly | Annual |
|----------|---------|--------|
| Idle EC2 | $2,400 | $28,800 |
| Unattached EBS | $500 | $6,000 |
| Unused NAT Gateways | $1,080 | $12,960 |
| **Total** | **$4,730** | **$56,760** |

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 License

MIT License - see [LICENSE](LICENSE)

## 🌟 Support

- ⭐ Star this repo
- 🐛 [Report bugs](https://github.com/shivajichaprana/kloudkut/issues)
- 💡 [Request features](https://github.com/shivajichaprana/kloudkut/issues)
- 💬 [Discussions](https://github.com/shivajichaprana/kloudkut/discussions)

---

Made with ❤️ by the KloudKut community
