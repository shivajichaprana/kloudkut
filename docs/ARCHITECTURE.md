# KloudKut Architecture

## Overview

KloudKut is a modular AWS cost optimization tool designed for scalability, performance, and extensibility.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI / API                            │
│                    (main.py / dashboard.py)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                      Core Layer                              │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Scanner  │  Config  │   AWS    │ Metrics  │  Notify  │  │
│  │  Base    │  Loader  │ Clients  │ Helper   │  System  │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │Telemetry │  Health  │  Retry   │Validation│ History  │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                    Scanner Layer                             │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Compute  │ Database │ Storage  │ Network  │ Security │  │
│  │ Scanners │ Scanners │ Scanners │ Scanners │ Scanners │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│  ┌──────────┬──────────┐                                    │
│  │Analytics │Management│                                    │
│  │ Scanners │ Scanners │                                    │
│  └──────────┴──────────┘                                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                    AWS Services                              │
│  EC2 │ RDS │ S3 │ Lambda │ CloudWatch │ ... (45 services)  │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Scanner Base (`core/scanner.py`)
- Abstract base class for all scanners
- Parallel execution with ThreadPoolExecutor
- Caching with TTL (1 hour default)
- Error isolation per region
- Automatic cost sorting

### 2. AWS Client Factory (`core/aws.py`)
- LRU cached boto3 clients
- Region-aware client creation
- Session management for multi-account

### 3. Configuration (`core/config.py`)
- YAML-based configuration
- Environment variable substitution
- Merge default + user config
- Path traversal protection

### 4. Metrics Helper (`core/metrics.py`)
- CloudWatch data fetching
- Batched queries for efficiency
- Configurable time windows

### 5. Telemetry (`core/telemetry.py`)
- Performance tracking
- Scan duration metrics
- Error tracking
- Summary statistics

### 6. Health Checks (`core/health.py`)
- AWS credential validation
- Permission checking
- System status monitoring

### 7. Retry Logic (`core/retry.py`)
- Exponential backoff
- Rate limit handling
- Configurable max retries

## Data Flow

```
1. User Input (CLI/API)
   ↓
2. Load Configuration
   ↓
3. Initialize Scanners
   ↓
4. Parallel Region Scanning
   ↓
5. Aggregate Findings
   ↓
6. Sort by Cost
   ↓
7. Generate Reports
   ↓
8. Send Notifications
   ↓
9. Save to History
```

## Scanner Lifecycle

```python
1. __init__(config, regions)
   - Load service-specific config
   - Store regions list
   - Calculate config hash

2. scan(use_cache=True)
   - Check cache (if enabled)
   - Parallel scan_region() calls
   - Aggregate results
   - Sort by cost
   - Cache results

3. scan_region(region)
   - Get AWS client
   - Fetch resources
   - Check CloudWatch metrics
   - Apply thresholds
   - Return findings
```

## Caching Strategy

- **Key**: `service:regions:config_hash`
- **TTL**: 3600 seconds (1 hour)
- **Storage**: Local JSON files in `.kloudkut_cache/`
- **Invalidation**: Config changes, manual clear

## Parallel Execution

- **Workers**: min(regions, 10)
- **Timeout**: 300 seconds per scanner
- **Error Handling**: Isolated per region
- **Progress**: tqdm progress bars

## Security Features

1. **Path Traversal Protection**
   - Input validation on all file paths
   - Whitelist-based directory access

2. **Input Sanitization**
   - Tag key/value sanitization
   - Region format validation
   - Account ID validation

3. **Credential Management**
   - No credentials stored
   - Uses AWS SDK credential chain
   - Supports IAM roles

4. **API Rate Limiting**
   - Exponential backoff
   - Automatic retry logic
   - Respects AWS limits

## Performance Optimizations

1. **Parallel Scanning**
   - ThreadPoolExecutor for regions
   - Concurrent AWS API calls

2. **Caching**
   - 1-hour TTL reduces API calls
   - Config-aware cache keys

3. **Batched Queries**
   - CloudWatch metrics batching
   - Paginated resource fetching

4. **Lazy Loading**
   - On-demand client creation
   - LRU cache for clients

## Extensibility

### Adding New Scanner

```python
from kloudkut import BaseScanner, Finding

class NewServiceScanner(BaseScanner):
    service = "NEWSERVICE"
    
    def scan_region(self, region: str) -> list[Finding]:
        client = get_client("newservice", region)
        # Scan logic
        return findings
```

### Custom Thresholds

```yaml
resources:
  NEWSERVICE:
    threshold: 10
    exclude_tags:
      Environment: production
```

## Monitoring & Observability

1. **Telemetry**
   - Scan duration tracking
   - Finding counts
   - Error rates

2. **Health Checks**
   - Credential validation
   - Permission verification
   - System status

3. **Logging**
   - Structured logging
   - Configurable levels
   - Error tracking

## Deployment Options

1. **CLI** - Local execution
2. **Docker** - Containerized
3. **Lambda** - Serverless
4. **Dashboard** - Web UI
5. **CI/CD** - Automated scans

## Multi-Account Support

```bash
kloudkut --accounts 111111111111 222222222222 \
         --role-name OrganizationAccountAccessRole
```

Uses STS AssumeRole to scan multiple accounts with a single command.
