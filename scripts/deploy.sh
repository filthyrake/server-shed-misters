#!/bin/bash

# Production deployment script for Mister Controller
set -e

DEPLOY_DIR="/opt/mister-controller"
SERVICE_NAME="mister-controller"

echo "🚀 Deploying Mister Controller to production..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root for production deployment"
    exit 1
fi

# Create deployment directory
echo "📁 Creating deployment directory..."
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# Copy application files
echo "📋 Copying application files..."
if [ -d "/tmp/mister-controller-src" ]; then
    cp -r /tmp/mister-controller-src/* $DEPLOY_DIR/
else
    echo "❌ Source files not found in /tmp/mister-controller-src"
    echo "   Please copy your source files there first"
    exit 1
fi

# Check for .env file
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo "❌ .env file not found!"
    echo "   Please copy your .env file to $DEPLOY_DIR/"
    exit 1
fi

# Set up Docker secrets
echo "🔐 Setting up Docker secrets..."
if [ -f "$DEPLOY_DIR/scripts/setup-secrets.sh" ]; then
    cd $DEPLOY_DIR
    ./scripts/setup-secrets.sh
else
    echo "⚠️  Warning: setup-secrets.sh not found, skipping secrets setup"
    echo "   Secrets will need to be configured manually or using environment variables"
fi

# Set permissions
echo "🔒 Setting permissions..."
chown -R root:docker $DEPLOY_DIR
chmod -R 755 $DEPLOY_DIR
chmod 600 $DEPLOY_DIR/.env
# Set restrictive permissions for secrets directory
if [ -d "$DEPLOY_DIR/secrets" ]; then
    chmod 700 $DEPLOY_DIR/secrets
    chmod 600 $DEPLOY_DIR/secrets/* 2>/dev/null || true
fi

# Install systemd service
echo "⚙️ Installing systemd service..."
cp $DEPLOY_DIR/systemd/mister-controller.service /etc/systemd/system/
systemctl daemon-reload

# Build Docker image
echo "🐳 Building Docker image..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Stop existing service if running
echo "🛑 Stopping existing service..."
systemctl stop $SERVICE_NAME || true

# Start the service
echo "▶️ Starting service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Wait for health check
echo "🩺 Waiting for health check..."
sleep 30

# Check if service is healthy
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Service is healthy and running!"
    echo "🌐 Web UI available at: http://$(hostname -I | awk '{print $1}'):8000"
    
    # Show status
    echo ""
    echo "📊 Service Status:"
    systemctl status $SERVICE_NAME --no-pager -l
    
    echo ""
    echo "📝 Recent logs:"
    journalctl -u $SERVICE_NAME --no-pager -l -n 10
    
else
    echo "❌ Service failed health check!"
    echo "📝 Checking logs..."
    journalctl -u $SERVICE_NAME --no-pager -l -n 20
    exit 1
fi

echo ""
echo "🎉 Deployment complete!"
echo "   - Service: systemctl status $SERVICE_NAME"
echo "   - Logs: journalctl -u $SERVICE_NAME -f"
echo "   - Web UI: http://localhost:8000"