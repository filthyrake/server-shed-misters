# Docker Secrets Configuration

This directory contains Docker secrets files for API credentials. These files are mounted into the container at `/run/secrets/` and provide a secure way to pass credentials without exposing them in environment variables.

## Setup

Create three files in this directory with your API credentials:

```bash
# Create secret files
echo "your_switchbot_token_here" > switchbot_token
echo "your_switchbot_secret_here" > switchbot_secret
echo "your_rachio_api_token_here" > rachio_api_token

# Set restrictive permissions (important!)
chmod 600 switchbot_token switchbot_secret rachio_api_token
```

## Security Benefits

Using Docker secrets instead of environment variables:
- ✅ Credentials NOT visible in `docker inspect` output
- ✅ Credentials NOT visible in process lists
- ✅ Credentials NOT logged or exposed in container metadata
- ✅ Secrets stored as files with restricted permissions
- ✅ Secrets can be managed with file system permissions and encryption

## File Structure

```
secrets/
├── switchbot_token      # Your SwitchBot API token
├── switchbot_secret     # Your SwitchBot API secret
└── rachio_api_token     # Your Rachio API token
```

## Quick Setup Script

Run this script to set up secrets from your `.env` file:

```bash
#!/bin/bash
# scripts/setup-secrets.sh

set -e

SECRETS_DIR="./secrets"

# Source .env file
if [ -f ".env" ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

# Create secrets directory
mkdir -p "$SECRETS_DIR"

# Create secret files
echo "$SWITCHBOT_TOKEN" > "$SECRETS_DIR/switchbot_token"
echo "$SWITCHBOT_SECRET" > "$SECRETS_DIR/switchbot_secret"
echo "$RACHIO_API_TOKEN" > "$SECRETS_DIR/rachio_api_token"

# Set restrictive permissions
chmod 600 "$SECRETS_DIR/switchbot_token"
chmod 600 "$SECRETS_DIR/switchbot_secret"
chmod 600 "$SECRETS_DIR/rachio_api_token"

echo "✅ Secrets configured successfully"
echo "   Secrets directory: $SECRETS_DIR"
echo "   Files created with 600 permissions (read/write for owner only)"
```

## Migration from Environment Variables

If you're currently using environment variables (`.env` file), you can migrate to secrets:

1. **Create secret files from .env**:
   ```bash
   ./scripts/setup-secrets.sh
   ```

2. **Restart containers**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **(Optional) Remove credentials from .env**:
   After verifying secrets work, you can remove the credential lines from `.env`:
   ```bash
   # Remove these lines from .env (keep device IDs and thresholds)
   # SWITCHBOT_TOKEN=...
   # SWITCHBOT_SECRET=...
   # RACHIO_API_TOKEN=...
   ```

## Fallback Behavior

The application supports both secrets and environment variables with this priority:
1. **Docker secrets** (files in `/run/secrets/`) - preferred
2. **Environment variables** - fallback for development

This allows:
- Production to use secure Docker secrets
- Development to use `.env` file for convenience
- Backward compatibility with existing deployments

## Production Deployment

For production, use secrets exclusively:

```bash
# 1. Create secrets from .env
./scripts/setup-secrets.sh

# 2. Deploy with production config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Verify secrets are being used (check logs)
docker-compose logs | grep "Loaded secret"

# 4. Verify credentials NOT visible
docker inspect mister-controller | grep -i token
# Should show empty or "***" but not actual tokens
```

## Verification

To verify your secrets are working:

```bash
# Check that secrets are mounted
docker exec mister-controller ls -l /run/secrets/
# Should show: switchbot_token, switchbot_secret, rachio_api_token

# Check container logs for secret loading
docker-compose logs | grep "Loaded secret"
# Should show: "Loaded secret 'switchbot_token' from Docker secrets"

# Verify credentials NOT in environment
docker exec mister-controller env | grep -i token
# Should be empty or show fallback placeholder

# Verify credentials NOT in inspect
docker inspect mister-controller | grep -i -A5 -B5 "SWITCHBOT"
# Should not show actual token values
```

## Troubleshooting

### "Secret file not found" error

Make sure secret files exist and have correct permissions:
```bash
ls -l secrets/
chmod 600 secrets/*
```

### "Permission denied" on secret files

Ensure the Docker user can read the files:
```bash
chmod 600 secrets/*
chown $USER:$USER secrets/*
```

### Application still using environment variables

Check container logs to see which method is being used:
```bash
docker-compose logs | grep "Loaded secret"
```

If it shows "from environment variable" instead of "from Docker secrets", verify:
1. Secret files exist in `./secrets/`
2. docker-compose.yml has `secrets:` section configured
3. Container was rebuilt after adding secrets

## Additional Resources

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [Security Best Practices](../SECURITY.md)
- [Production Deployment Guide](../README-Production.md)
