# Contributing to KloudKut

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/shivajichaprana/kloudkut.git`
3. Create a virtual environment: `python3 -m venv venv && source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt pytest pytest-cov`
5. Create a branch: `git checkout -b feature/your-feature`

## Development

### Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=kloudkut  # With coverage
```

### Adding a New Scanner

1. Create scanner class in appropriate file under `kloudkut/scanners/`
2. Inherit from `BaseScanner`
3. Implement `scan_region(region: str) -> list[Finding]`
4. Add to `ALL_SCANNERS` in `kloudkut/scanners/__init__.py`
5. Add default config to `config/default.yaml`
6. Write tests in `tests/`

Example:
```python
from kloudkut.core import BaseScanner, Finding, get_client

class NewServiceScanner(BaseScanner):
    service = "NEWSERVICE"
    
    def scan_region(self, region: str) -> list[Finding]:
        client = get_client("newservice", region)
        findings = []
        # Your scanning logic here
        return findings
```

### Code Style

- Follow PEP 8
- Use type hints
- Keep functions focused and small
- Add docstrings for public APIs

## Pull Request Process

1. Update README.md if adding new features
2. Add tests for new functionality
3. Ensure all tests pass
4. Update service count if adding scanners
5. Submit PR with clear description

## Questions?

Open an issue for discussion before major changes.
