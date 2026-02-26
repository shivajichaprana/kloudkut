.PHONY: help install install-dev test lint format clean docker benchmark

help:
	@echo "KloudKut Development Commands"
	@echo ""
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Run linters (ruff, mypy)"
	@echo "  make format       - Format code with black and ruff"
	@echo "  make clean        - Remove cache and build artifacts"
	@echo "  make docker       - Build Docker image"
	@echo "  make benchmark    - Run performance benchmarks"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt
	pip install -e .

test:
	pytest tests/ -v --cov=kloudkut --cov-report=term --cov-report=html

lint:
	ruff check kloudkut/
	mypy kloudkut/ --ignore-missing-imports

format:
	black kloudkut/ tests/
	ruff check --fix kloudkut/

clean:
	rm -rf .kloudkut_cache/ .pytest_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker:
	docker build -t kloudkut:latest .

benchmark:
	python benchmark.py
