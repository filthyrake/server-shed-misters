#!/bin/bash

# Backup script for Mister Controller data and configuration
set -e

BACKUP_DIR="/opt/mister-controller/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="mister-controller-backup-$TIMESTAMP.tar.gz"

echo "💾 Creating backup of Mister Controller..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

# Determine volume name (try auto-detection, fallback to default)
VOLUME_NAME="mister-controller_mister-data"
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "❌ Volume $VOLUME_NAME not found"
    echo "Available volumes:"
    docker volume ls | grep mister || echo "  No mister volumes found"
    echo ""
    echo "💡 Tip: Volume name depends on docker-compose project name."
    echo "   Check with: docker volume ls | grep mister"
    exit 1
fi

# Create backup directory
mkdir -p $BACKUP_DIR

# Create temporary backup directory
TEMP_BACKUP="/tmp/mister-backup-$TIMESTAMP"
mkdir -p $TEMP_BACKUP

# Copy configuration
echo "📋 Backing up configuration..."
cp /opt/mister-controller/.env $TEMP_BACKUP/

# Export Docker volume data
echo "📦 Backing up persistent data..."
docker run --rm -v $VOLUME_NAME:/data -v $TEMP_BACKUP:/backup busybox tar czf /backup/data.tar.gz -C /data .

# Export Docker image
echo "🐳 Backing up Docker image..."
docker save mister-controller_mister-controller:latest | gzip > $TEMP_BACKUP/docker-image.tar.gz

# Get service status
echo "📊 Backing up service status..."
systemctl is-active mister-controller > $TEMP_BACKUP/service-status.txt || echo "inactive" > $TEMP_BACKUP/service-status.txt
systemctl is-enabled mister-controller > $TEMP_BACKUP/service-enabled.txt || echo "disabled" > $TEMP_BACKUP/service-enabled.txt

# Create final backup archive
echo "🗜️ Creating backup archive..."
tar czf "$BACKUP_DIR/$BACKUP_FILE" -C /tmp "mister-backup-$TIMESTAMP"

# Clean up
rm -rf $TEMP_BACKUP

# Verify backup was created and is not empty
if [ ! -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    echo "❌ Backup file was not created"
    exit 1
fi

# Check backup size (use appropriate stat command based on OS)
if command -v stat > /dev/null 2>&1; then
    if stat --version 2>&1 | grep -q GNU; then
        # GNU stat (Linux)
        BACKUP_SIZE=$(stat -c%s "$BACKUP_DIR/$BACKUP_FILE")
    else
        # BSD stat (macOS)
        BACKUP_SIZE=$(stat -f%z "$BACKUP_DIR/$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_DIR/$BACKUP_FILE")
    fi
    
    if [ "$BACKUP_SIZE" -lt 1000 ]; then
        echo "⚠️  Warning: Backup file is suspiciously small ($BACKUP_SIZE bytes)"
    fi
fi

# Keep only last 7 backups
echo "🧹 Cleaning old backups..."
cd $BACKUP_DIR
ls -t mister-controller-backup-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm

echo "✅ Backup created: $BACKUP_DIR/$BACKUP_FILE"
echo "📁 Backup size: $(du -sh $BACKUP_DIR/$BACKUP_FILE | cut -f1)"
echo "🗂️ Available backups:"
ls -lah $BACKUP_DIR/mister-controller-backup-*.tar.gz 2>/dev/null || echo "  Current backup is the only one"