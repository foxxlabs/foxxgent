# FoxxGent Security Policy

This document outlines the security practices and policies for FoxxGent, an AI-powered AI agent.

## Supported Versions

The following versions of FoxxGent are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

Only the latest stable release receives security patches. We recommend always running the most recent version.

## Reporting Vulnerabilities

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### Reporting Channels

1. **GitHub Security Advisories**: Submit a vulnerability report via [GitHub Security Advisories](https://github.com/foxxgent/foxxgent/security/advisories/new)
2. **Email**: For critical issues, contact the maintainers directly

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Fix Timeline**: Depends on severity (critical issues are prioritized)

## Vulnerability Report Guidelines

When reporting a vulnerability, please include:

### Required Information

- **Description**: Clear explanation of the vulnerability
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Severity**: Your assessment of the impact (Critical/High/Medium/Low)
- **Affected Components**: Which parts of FoxxGent are affected

### Recommended Information

- Proof of concept or exploit code (if available)
- Potential remediation suggestions
- Any relevant logs or error messages

### What to Avoid

- Do not publicly disclose vulnerabilities before coordinating with maintainers
- Do not attempt to exploit vulnerabilities beyond what's necessary for proof of concept
- Do not target other users or systems

## Security Best Practices for Users

### 1. Change Default Secrets

Never run FoxxGent with default or example secrets in production.

```bash
# Required: Change these in your .env file
SECRET_KEY=your_production_secret_key_minimum_32_chars
FOXXGENT_SECRET_KEY=your_unique_production_secret
```

- Use cryptographically strong random values (minimum 32 characters)
- Store secrets outside of version control
- Rotate secrets periodically

### 2. Use Strong API Keys

- Use API keys with minimal required permissions
- Never commit API keys to version control
- Rotate API keys regularly
- Use environment variables, not hardcoded values

### 3. Run in Docker for Isolation

Running FoxxGent in Docker provides important security boundaries:

```bash
# Use the provided Docker setup
docker-compose up -d
```

Benefits:
- Process isolation from host system
- Limited filesystem access
- Controlled network exposure
- Easier security updates via container recreation

### 4. Don't Expose to Public Internet Without Authentication

- Never expose FoxxGent directly to the public internet without proper authentication
- Use reverse proxies with authentication (nginx, traefik)
- Consider VPN or wireguard for remote access
- Use firewall rules to restrict access to trusted IPs

### 5. Keep Dependencies Updated

Regularly update dependencies to patch known vulnerabilities:

```bash
# Update Python dependencies
pip install -r requirements.txt

# Rebuild Docker containers
docker-compose build --no-cache
```

Subscribe to security advisories for your dependencies.

### 6. Secure Your Environment

- Run FoxxGent with a dedicated system user (not root)
- Use SELinux or AppArmor if available
- Enable automatic security updates for your operating system
- Monitor logs for suspicious activity

## Telegram Pairing Security

The Telegram pairing mechanism provides device authentication. Be aware of the following:

### Pairing Code Security

- Pairing codes are generated fresh on each server restart
- Codes are displayed in the server console only
- Anyone with access to the server console can see the current code
- The pairing process creates a trusted device association via `chat_id`

### Security Recommendations

1. **Restrict Console Access**: Only trusted users should have access to the server terminal
2. **Use in Private Chats**: Pair your bot in private conversations, not group chats
3. **Revoke Untrusted Devices**: Use `/unpair` command to revoke access from lost devices
4. **Enable 2FA on Telegram**: Add extra protection to your Telegram account

### What Telegram Access Can Do

Once paired, a device can:
- Send commands to control your server
- Access system information (CPU, memory, disk)
- Execute shell commands based on AI decisions
- Access connected third-party services (Gmail, Calendar, etc.)

Only pair devices you trust completely.

## Security Updates & Changelog

Security updates are documented in the project release notes. We recommend:

1. Watching the GitHub repository for releases
2. Reviewing security advisories periodically
3. Enabling automatic dependency updates (with testing)

### Release Note Format

Security fixes are marked with a :shield: emoji in release notes.

## Contact Information

- **General Issues**: [GitHub Issues](https://github.com/foxxgent/foxxgent/issues)
- **Security Advisories**: [Security Advisories](https://github.com/foxxgent/foxxgent/security/advisories)
- **Email**: Contact via GitHub for sensitive issues

## Disclosure Policy

We follow a coordinated disclosure process:

1. Reporter submits vulnerability details
2. Team verifies and confirms the issue
3. Development team works on a fix
4. Fix is tested and reviewed
5. Security advisory is published with the fix
6. Users are notified to update

## Security Acknowledgments

We appreciate the security community's efforts to improve FoxxGent's security. Contributors who report vulnerabilities will be acknowledged (with permission) in the security advisory.

---

*Last updated: March 2026*
