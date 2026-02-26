# Troubleshooting Guide

## Common Issues

### AWS Credentials Not Found

**Error:** `NoCredentialsError: Unable to locate credentials`

**Solution:**
```bash
# Option 1: Configure AWS CLI
aws configure

# Option 2: Set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# Option 3: Use IAM role (EC2/ECS/Lambda)
# No configuration needed - automatic
```

### Permission Denied Errors

**Error:** `AccessDeniedException` or `UnauthorizedOperation`

**Solution:** Ensure your IAM user/role has required permissions. See README for minimum IAM policy.

### Rate Limiting / Throttling

**Error:** `ThrottlingException` or `RequestLimitExceeded`

**Solution:**
- Reduce number of regions: `python main.py --regions us-east-1`
- Scan specific services: `python main.py --services EC2 RDS`
- Wait and retry - KloudKut has built-in retry logic

### No Findings Returned

**Possible causes:**
1. No idle resources (good news!)
2. Insufficient permissions to read metrics
3. Resources are in regions not being scanned

**Solution:**
```bash
# Enable verbose logging
python main.py --verbose

# Check specific region
python main.py --regions us-east-1 --verbose
```

### Cache Issues

**Problem:** Stale or incorrect results

**Solution:**
```bash
# Clear cache
python main.py --clear-cache

# Disable cache for fresh scan
python main.py --no-cache
```

### Dashboard Not Loading

**Error:** `Address already in use`

**Solution:**
```bash
# Check if port 5000 is in use
lsof -i :5000  # macOS/Linux
netstat -ano | findstr :5000  # Windows

# Kill the process or use different port
# Edit dashboard.py and change port number
```

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'kloudkut'`

**Solution:**
```bash
# Ensure you're in project root
cd /path/to/KloudKut

# Reinstall dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

### Python Version Issues

**Error:** `SyntaxError` or version-related errors

**Solution:**
```bash
# Check Python version (requires 3.12+)
python3 --version

# Use specific Python version
python3.12 main.py
```

## Performance Tips

1. **Scan specific regions:** Reduces API calls significantly
   ```bash
   python main.py --regions us-east-1 eu-west-1
   ```

2. **Use caching:** Default behavior, speeds up repeated scans
   ```bash
   python main.py  # Uses cache (1 hour TTL)
   ```

3. **Parallel execution:** Already optimized (10 workers per service)

4. **Target specific services:** When you know what to check
   ```bash
   python main.py --services EC2 RDS S3
   ```

## Getting Help

1. Check existing [GitHub Issues](https://github.com/shivajichaprana/kloudkut/issues)
2. Enable verbose logging: `--verbose`
3. Open a new issue with:
   - Error message
   - Command used
   - Python version
   - AWS region(s)
