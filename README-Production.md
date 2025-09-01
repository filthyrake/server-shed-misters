# Mister Controller - Production Deployment

A production-ready automated temperature and humidity control system for server sheds.

## Features

- **🌡️ Real-time monitoring** - SwitchBot Hub 2 temperature/humidity sensors
- **💦 Smart misting** - Rachio Smart Hose Timer valve control  
- **🌐 Web interface** - Simple control panel for pause/resume
- **📊 State persistence** - Remembers settings across restarts
- **🔄 Auto-recovery** - Restarts automatically if crashed
- **📦 Dockerized** - Easy deployment and updates
- **🩺 Health checks** - Built-in monitoring and alerts
- **💾 Backup/restore** - Data protection and migration

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- systemd (Linux)
- Your API credentials

### 2. Deploy

```bash
# Copy source files to server
scp -r . user@server:/tmp/mister-controller-src

# SSH to server and deploy
ssh user@server
sudo /tmp/mister-controller-src/scripts/deploy.sh
```

### 3. Access

- **Web UI**: http://your-server:8000
- **API**: http://your-server:8000/api/status
- **Logs**: `journalctl -u mister-controller -f`

## Configuration

### Environment Variables

All settings are configured via the `.env` file:

```bash
# API Credentials (Required)
SWITCHBOT_TOKEN=your_switchbot_token
SWITCHBOT_SECRET=your_switchbot_secret  
RACHIO_API_TOKEN=your_rachio_token

# Device IDs (Required)
HUB2_DEVICE_ID=your_hub2_id
RACHIO_VALVE_ID=your_valve_id

# Thresholds (Optional)
TEMP_HIGH=95          # Start misting above this temp (°F)
TEMP_LOW=95           # Stop misting below this temp (°F)
HUMIDITY_LOW=35       # Start misting below this humidity (%)
HUMIDITY_HIGH=35      # Stop misting above this humidity (%)

# Timing (Optional)
MISTER_DURATION=600   # Run for 10 minutes (seconds)
CHECK_INTERVAL=60     # Check sensors every 1 minute (seconds)
COOLDOWN_SECONDS=300  # Wait 5 minutes between cycles (seconds)
```

## Management Commands

### Service Management

```bash
# Check status
systemctl status mister-controller

# Start/stop/restart
sudo systemctl start mister-controller
sudo systemctl stop mister-controller
sudo systemctl restart mister-controller

# View logs
journalctl -u mister-controller -f

# Check Docker containers
docker-compose ps
```

### Web Interface

Visit http://your-server:8000 to:
- View current temperature/humidity
- See misting status
- Pause/resume the system
- Monitor system health

### API Endpoints

```bash
# Get status
curl http://localhost:8000/api/status

# Control system
curl -X POST http://localhost:8000/api/pause
curl -X POST http://localhost:8000/api/resume
curl -X POST http://localhost:8000/api/stop
curl -X POST http://localhost:8000/api/start

# Health check
curl http://localhost:8000/health
```

## Backup & Recovery

### Create Backup

```bash
sudo /opt/mister-controller/scripts/backup.sh
```

### Restore from Backup

```bash
sudo /opt/mister-controller/scripts/restore.sh /path/to/backup.tar.gz
```

### Automatic Backups

Add to crontab for daily backups:

```bash
# Add to root crontab
echo "0 2 * * * /opt/mister-controller/scripts/backup.sh" | sudo crontab -
```

## Monitoring & Alerting

### Health Checks

The system includes multiple health checks:
- HTTP health endpoint (`/health`)
- Docker container health checks
- systemd service monitoring
- Automatic restart on failure

### Log Monitoring

Monitor logs for issues:

```bash
# Follow logs in real-time
journalctl -u mister-controller -f

# Search for errors
journalctl -u mister-controller | grep -i error

# View recent startup logs
journalctl -u mister-controller --since "10 minutes ago"
```

### System Statistics

The web interface shows:
- Uptime and restart counts
- Crash detection and recovery
- API connection status
- Recent misting activity

## Troubleshooting

### Service Won't Start

```bash
# Check systemd status
systemctl status mister-controller

# Check Docker logs
docker-compose logs

# Verify .env file
cat /opt/mister-controller/.env
```

### API Connection Issues

```bash
# Test SwitchBot API
curl -H "Authorization: YOUR_TOKEN" https://api.switch-bot.com/v1.1/devices

# Test Rachio API  
curl -H "Authorization: Bearer YOUR_TOKEN" https://api.rach.io/1/public/person/info

# Check network connectivity
ping api.switch-bot.com
ping api.rach.io
```

### Web UI Not Accessible

```bash
# Check if port is bound
netstat -tlnp | grep :8000

# Check firewall
sudo ufw status
sudo iptables -L

# Test locally
curl http://localhost:8000/health
```

### Data Loss Recovery

If state is lost:

```bash
# Check persistent volume
docker volume inspect mister-controller_mister-data

# Restore from backup
sudo /opt/mister-controller/scripts/restore.sh /path/to/backup.tar.gz
```

## Security Considerations

### Credentials
- Store `.env` file with restricted permissions (600)
- Use environment variables for sensitive data
- Rotate API tokens periodically

### Network Security
- Run behind reverse proxy (nginx/traefik) in production
- Enable HTTPS with SSL certificates
- Restrict access to management interfaces

### Access Control
- Consider adding authentication to web interface
- Use firewall rules to limit access
- Monitor access logs

## Updates & Maintenance

### Update Application

```bash
# Stop service
sudo systemctl stop mister-controller

# Update source code
cd /opt/mister-controller
git pull origin main  # or copy new files

# Rebuild and restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
sudo systemctl start mister-controller
```

### Update Dependencies

```bash
# Update base images
docker-compose pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Maintenance Schedule

Recommended maintenance tasks:
- **Daily**: Check logs and system status
- **Weekly**: Review performance metrics
- **Monthly**: Update dependencies and create backups
- **Quarterly**: Review and rotate API credentials

## Performance Tuning

### Resource Limits

Adjust in `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 256M
      cpus: '0.5'
```

### Monitoring Intervals

Adjust check intervals based on needs:
- Faster response: `CHECK_INTERVAL=30` (30 seconds)
- Lower API usage: `CHECK_INTERVAL=120` (2 minutes)

### Logging

Adjust log retention:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "5"
```

## Support

For issues:
1. Check logs: `journalctl -u mister-controller -f`
2. Verify configuration: `systemctl status mister-controller`
3. Test API connections manually
4. Review backup/restore procedures