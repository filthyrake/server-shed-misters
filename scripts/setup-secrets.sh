#!/bin/bash

# Setup Docker secrets from .env file
# This script creates secret files from environment variables

set -e

SECRETS_DIR="./secrets"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🔐 Setting up Docker secrets..."

# Check for .env file
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "   Please create a .env file with your API credentials"
    echo "   You can copy .env.example to .env and fill in your credentials"
    exit 1
fi

# Parse .env file securely (only extract required variables, don't source entire file)
# This prevents accidentally exposing all environment variables
# Using sed to handle values containing '=' characters correctly
SWITCHBOT_TOKEN=$(grep -E "^SWITCHBOT_TOKEN=" .env | sed 's/^SWITCHBOT_TOKEN=//' | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
SWITCHBOT_SECRET=$(grep -E "^SWITCHBOT_SECRET=" .env | sed 's/^SWITCHBOT_SECRET=//' | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
RACHIO_API_TOKEN=$(grep -E "^RACHIO_API_TOKEN=" .env | sed 's/^RACHIO_API_TOKEN=//' | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")

# Validate required variables
if [ -z "$SWITCHBOT_TOKEN" ] || [ -z "$SWITCHBOT_SECRET" ] || [ -z "$RACHIO_API_TOKEN" ]; then
    echo "❌ Error: Missing required credentials in .env file"
    echo "   Required: SWITCHBOT_TOKEN, SWITCHBOT_SECRET, RACHIO_API_TOKEN"
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
echo "   Files created:"
echo "     - switchbot_token (600 permissions)"
echo "     - switchbot_secret (600 permissions)"
echo "     - rachio_api_token (600 permissions)"
echo ""
echo "Next steps:"
echo "   1. Start the container: docker-compose up -d"
echo "   2. Check logs: docker-compose logs | grep 'Loaded secret'"
echo "   3. Verify security: docker inspect mister-controller | grep -i token"
