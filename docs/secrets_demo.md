# Docker Secrets Security Demo

This document demonstrates how the Docker secrets implementation addresses the security vulnerability where API credentials were visible in `docker inspect` and process lists.

## The Problem (Before)

Previously, credentials were passed as environment variables in docker-compose.yml:

```yaml
environment:
  - SWITCHBOT_TOKEN=${SWITCHBOT_TOKEN}
  - SWITCHBOT_SECRET=${SWITCHBOT_SECRET}
  - RACHIO_API_TOKEN=${RACHIO_API_TOKEN}
```

This made credentials visible in:
1. `docker inspect mister-controller` output
2. Container environment inspection
3. Process listings on the host

## The Solution (After)

Now credentials are loaded from Docker secrets with environment variable fallback:

```yaml
secrets:
  - switchbot_token
  - switchbot_secret
  - rachio_api_token

secrets:
  switchbot_token:
    file: ./secrets/switchbot_token
  switchbot_secret:
    file: ./secrets/switchbot_secret
  rachio_api_token:
    file: ./secrets/rachio_api_token
```

## Setup Instructions

### 1. Create Secret Files

```bash
# Automatic setup from .env file
./scripts/setup-secrets.sh

# Or manual setup
echo "your_switchbot_token" > secrets/switchbot_token
echo "your_switchbot_secret" > secrets/switchbot_secret
echo "your_rachio_api_token" > secrets/rachio_api_token
chmod 600 secrets/*
```

### 2. Start Container

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 3. Verify Security

```bash
# Check that secrets are loaded (should show "from Docker secrets")
docker-compose logs | grep "Loaded secret"

# Verify credentials NOT visible in docker inspect
docker inspect mister-controller | grep -i "SWITCHBOT_TOKEN"
# Should show empty or "-" but NOT the actual token

# Verify secrets are mounted correctly
docker exec mister-controller ls -l /run/secrets/
# Should show: switchbot_token, switchbot_secret, rachio_api_token
```

## Security Verification Commands

### Test 1: Docker Inspect (Should NOT expose credentials)

```bash
# Before (INSECURE): Would show actual token values
# docker inspect mister-controller | grep -A2 "SWITCHBOT_TOKEN"
# Result: "SWITCHBOT_TOKEN=your_actual_token_here"

# After (SECURE): Shows empty or placeholder
docker inspect mister-controller | grep -A2 "SWITCHBOT_TOKEN"
# Result: "SWITCHBOT_TOKEN=-" or "SWITCHBOT_TOKEN="
```

### Test 2: Process List (Should NOT expose credentials)

```bash
# Check process list on host
ps aux | grep python | grep -i token
# Should NOT show actual token values

# Check inside container
docker exec mister-controller ps aux
# Should NOT show actual token values in command line
```

### Test 3: Environment Variables (Should be empty or placeholder)

```bash
# Check container environment
docker exec mister-controller env | grep -i token
# Should show empty or placeholder values, not actual tokens
```

### Test 4: Secrets are Loaded Correctly

```bash
# Check application logs to verify secrets are loaded
docker-compose logs | grep "Loaded secret"

# Expected output:
# INFO - Loaded secret 'switchbot_token' from Docker secrets
# INFO - Loaded secret 'switchbot_secret' from Docker secrets
# INFO - Loaded secret 'rachio_api_token' from Docker secrets
```

## Comparison: Before vs After

| Aspect | Before (Environment Variables) | After (Docker Secrets) |
|--------|-------------------------------|------------------------|
| `docker inspect` | ✗ Shows actual tokens | ✓ Shows empty/placeholder |
| Process list | ✗ Tokens visible | ✓ Tokens NOT visible |
| Environment | ✗ Tokens in env vars | ✓ Empty/placeholder only |
| Container metadata | ✗ Tokens exposed | ✓ Tokens NOT exposed |
| File permissions | N/A | ✓ 600 (owner only) |
| Backward compatibility | N/A | ✓ Falls back to env vars |

## Security Benefits

1. **Credentials NOT in docker inspect**: The `docker inspect` command no longer reveals actual API tokens
2. **Credentials NOT in process list**: Process listings (`ps aux`) don't show tokens
3. **Credentials NOT in logs**: Container environment inspection doesn't expose secrets
4. **File-based permissions**: Secrets stored as files with restrictive OS permissions (600)
5. **Audit trail**: File access can be monitored via filesystem audit tools
6. **Encryption at rest**: Secret files can be encrypted using OS-level tools

## Fallback Behavior (Development)

For development environments, the system still supports environment variables:

```bash
# Development with .env file (no secrets directory needed)
cp .env.example .env
# Edit .env with your credentials
docker-compose up -d

# Application will log:
# INFO - Loaded secret 'switchbot_token' from environment variable SWITCHBOT_TOKEN
```

## Migration Guide

### For Existing Deployments

```bash
# 1. Pull latest code
git pull

# 2. Run setup script (reads from existing .env)
./scripts/setup-secrets.sh

# 3. Restart containers
docker-compose down
docker-compose up -d

# 4. Verify secrets are being used
docker-compose logs | grep "Loaded secret"

# 5. (Optional) Remove credentials from .env
# Keep device IDs and config, remove tokens
sed -i '/SWITCHBOT_TOKEN=/d' .env
sed -i '/SWITCHBOT_SECRET=/d' .env
sed -i '/RACHIO_API_TOKEN=/d' .env
```

### For New Deployments

```bash
# 1. Copy example and configure
cp .env.example .env
# Edit .env with your credentials

# 2. Set up secrets
./scripts/setup-secrets.sh

# 3. Deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Verify
docker-compose logs | grep "Loaded secret"
```

## Production Best Practices

1. **Use secrets exclusively**: Remove credentials from .env after migration
2. **Restrict file permissions**: Ensure secrets directory has 700 permissions
3. **Monitor access**: Use audit tools to monitor access to secrets files
4. **Rotate regularly**: Change API tokens quarterly and update secret files
5. **Backup encrypted**: If backing up secrets, ensure they're encrypted
6. **Separate environments**: Use different tokens for dev/staging/production

## Troubleshooting

### Issue: "Required secret not found"

```bash
# Check that secret files exist
ls -l secrets/
# Should show: switchbot_token, switchbot_secret, rachio_api_token

# Verify permissions
stat secrets/switchbot_token
# Should show: 600 (-rw-------)
```

### Issue: Still seeing tokens in docker inspect

```bash
# Ensure you're not using docker-compose.override.yml in production
docker-compose config | grep -A5 environment

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Issue: Application can't read secrets

```bash
# Check secrets are mounted in container
docker exec mister-controller ls -l /run/secrets/

# Check file contents (should be readable)
docker exec mister-controller cat /run/secrets/switchbot_token

# Check application logs
docker-compose logs | tail -50
```

## Additional Resources

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [secrets/README.md](../secrets/README.md) - Detailed setup guide
- [SECURITY.md](../SECURITY.md) - Security best practices
- [README-Production.md](../README-Production.md) - Production deployment

## References

This implementation addresses:
- GitHub Issue: Secrets exposed in process list and docker inspect output
- OWASP: [A02:2021 – Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
- CWE-526: Exposure of Sensitive Information Through Environmental Variables
