#!/bin/bash
# docker-entrypoint.sh
# Validates /app/data volume permissions before starting the application
set -e

echo "🔍 Checking /app/data volume permissions..."

# Check if data directory is writable
if [ ! -w /app/data ]; then
    echo "❌ ERROR: /app/data is not writable by user $(whoami)"
    echo "   Volume permissions may be incorrect"
    echo "   Fix with: docker run --rm -v mister-data:/data busybox chown -R 1000:1000 /data"
    exit 1
fi

# Test write
if ! touch /app/data/.write_test 2>/dev/null; then
    echo "❌ ERROR: Cannot write to /app/data"
    echo "   Check volume permissions and mount configuration"
    exit 1
fi
rm -f /app/data/.write_test

echo "✅ Volume permissions OK"

# Execute the CMD
exec "$@"
