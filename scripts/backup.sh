#!/bin/bash

# Backup script for Mister Controller data and configuration
set -e

BACKUP_DIR="/opt/mister-controller/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="mister-controller-backup-$TIMESTAMP.tar.gz"

echo "💾 Creating backup of Mister Controller..."

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
docker run --rm -v mister-controller_mister-data:/data -v $TEMP_BACKUP:/backup busybox tar czf /backup/data.tar.gz -C /data .

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

# Keep only last 7 backups
echo "🧹 Cleaning old backups..."
cd $BACKUP_DIR
ls -t mister-controller-backup-*.tar.gz | tail -n +8 | xargs -r rm

echo "✅ Backup created: $BACKUP_DIR/$BACKUP_FILE"
echo "📁 Backup size: $(du -sh $BACKUP_DIR/$BACKUP_FILE | cut -f1)"
echo "🗂️ Available backups:"
ls -lah $BACKUP_DIR/mister-controller-backup-*.tar.gz