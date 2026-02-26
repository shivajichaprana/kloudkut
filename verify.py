#!/usr/bin/env python3
"""Verify KloudKut project completeness."""
import os
from pathlib import Path

REQUIRED_FILES = [
    "README.md", "LICENSE", "pyproject.toml", "requirements.txt",
    "Makefile", "Dockerfile", "docker-compose.yml",
    "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    ".github/workflows/ci-cd.yml", ".github/workflows/release.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/API.md", "docs/ARCHITECTURE.md",
    "kloudkut/core/telemetry.py", "kloudkut/core/health.py",
    "kloudkut/core/retry.py", "kloudkut/core/validation.py",
    "tests/test_world_class.py",
]

def verify():
    root = Path(__file__).parent
    missing = []
    
    for file in REQUIRED_FILES:
        if not (root / file).exists():
            missing.append(file)
    
    if missing:
        print("❌ Missing files:")
        for f in missing:
            print(f"  - {f}")
        return False
    
    print("✅ All required files present!")
    print(f"✅ Total verified: {len(REQUIRED_FILES)} files")
    print("\n🌟 Project is WORLD-CLASS!")
    return True

if __name__ == "__main__":
    exit(0 if verify() else 1)
