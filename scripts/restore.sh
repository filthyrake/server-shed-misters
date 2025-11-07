#!/bin/bash

# Restore script for Mister Controller
set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-file>"
    echo "Available backups:"
    ls -lah /opt/mister-controller/backups/mister-controller-backup-*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEMP_RESTORE="/tmp/mister-restore-$TIMESTAMP"

echo "🔄 Restoring Mister Controller from backup: $BACKUP_FILE"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root"
    exit 1
fi

# Check backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

# Determine volume name (try auto-detection, fallback to default)
VOLUME_NAME="mister-controller_mister-data"
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "⚠️  Warning: Volume $VOLUME_NAME not found"
    echo "Available volumes:"
    docker volume ls | grep mister || echo "  No mister volumes found"
    echo ""
    echo "💡 Creating volume $VOLUME_NAME..."
    docker volume create "$VOLUME_NAME"
fi

# Extract backup
echo "📦 Extracting backup..."
mkdir -p $TEMP_RESTORE
tar xzf "$BACKUP_FILE" -C $TEMP_RESTORE --strip-components=1

# Stop service
echo "🛑 Stopping service..."
systemctl stop mister-controller || true

# Restore configuration
echo "📋 Restoring configuration..."
cp $TEMP_RESTORE/.env /opt/mister-controller/

# Restore data volume
echo "💾 Restoring data..."
if [ -f "$TEMP_RESTORE/data.tar.gz" ]; then
    docker run --rm -v $VOLUME_NAME:/data -v $TEMP_RESTORE:/backup busybox tar xzf /backup/data.tar.gz -C /data
else
    echo "⚠️  Warning: data.tar.gz not found in backup"
fi

# Restore Docker image
echo "🐳 Restoring Docker image..."
if [ -f "$TEMP_RESTORE/docker-image.tar.gz" ]; then
    gunzip -c $TEMP_RESTORE/docker-image.tar.gz | docker load
fi

# Restore service state
echo "⚙️ Restoring service state..."
if [ -f "$TEMP_RESTORE/service-enabled.txt" ]; then
    SERVICE_ENABLED=$(cat $TEMP_RESTORE/service-enabled.txt)
    if [ "$SERVICE_ENABLED" = "enabled" ]; then
        systemctl enable mister-controller
    fi
fi

if [ -f "$TEMP_RESTORE/service-status.txt" ]; then
    SERVICE_STATUS=$(cat $TEMP_RESTORE/service-status.txt)
    if [ "$SERVICE_STATUS" = "active" ]; then
        echo "▶️ Starting service..."
        systemctl start mister-controller
        
        # Wait for health check
        echo "🩺 Waiting for health check..."
        sleep 30
        
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ Service restored and healthy!"
        else
            echo "⚠️ Service started but health check failed"
        fi
    fi
fi

# Clean up
rm -rf $TEMP_RESTORE

echo "🎉 Restore complete!"
echo "📊 Service status:"
systemctl status mister-controller --no-pager -l