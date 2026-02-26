# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 5.x.x   | :white_check_mark: |
| < 5.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Email shivajichaprana@gmail.com with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and provide a timeline for fixes.

## Security Features

- Path traversal protection on all file operations
- Input validation and sanitization
- No credential storage (uses AWS SDK credential chain)
- Exponential backoff for API rate limiting
- Secure HTTP connections (HTTPS only)
- Regular dependency updates
- Automated security scanning (Trivy, CodeQL)

## Best Practices

1. **Credentials**: Use IAM roles instead of access keys when possible
2. **Permissions**: Follow principle of least privilege (ReadOnlyAccess recommended)
3. **Dashboard**: Enable authentication with `KLOUDKUT_TOKEN` environment variable
4. **Updates**: Keep KloudKut updated to latest version
5. **Network**: Run dashboard on trusted networks or localhost only

## Disclosure Policy

- Security issues are fixed in priority
- CVE assigned for critical vulnerabilities
- Public disclosure after fix is released
- Credit given to reporters (if desired)
