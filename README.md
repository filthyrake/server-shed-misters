# Server Shed Mister Controller

🌡️ **Automated temperature and humidity control system for server sheds**

A production-ready system that monitors SwitchBot Hub 2 sensors and controls Rachio Smart Hose Timer misters to keep your server environment cool and humid.

Ok ok ok, I know, this all sounds totally unhinged.  I have a backyard solar-powered server shed, and live in an EXTREMELY hot and dry climate.  To help with cooling, I have a DIY swamp cooler rigged up in the shed - the evaporative cooling works absolute wonders.  This is a service designed to automate my use of it.  Obviously the thing has been designed with my very specific and unusual use-case in mind, but maybe you can find something neat here.

I vibe coded this with Claude Code just to get something knocked out/usable.  This has lowered ambient temps in the shed by 10+F on hot days, which is a pretty huge deal when you're trying to keep servers cool.

## Features

- 🌡️ **Real-time monitoring** - SwitchBot Hub 2 temperature/humidity sensors
- 💦 **Smart misting** - Rachio Smart Hose Timer valve control  
- 🌐 **Web interface** - Simple control panel for pause/resume
- 📊 **State persistence** - Remembers settings across restarts
- 🔄 **Auto-recovery** - Restarts automatically if crashed
- 📦 **Dockerized** - Easy deployment and updates
- 🩺 **Health checks** - Built-in monitoring and alerts
- 💾 **Backup/restore** - Data protection and migration

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/damenknight/server-shed-misters.git
cd server-shed-misters
cp .env.example .env
# Edit .env with your API credentials
```

### 2. Run with Docker

```bash
# Development
docker-compose up -d

# Production  
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 3. Access

- **Web UI**: http://localhost:8000
- **API**: http://localhost:8000/api/status

## Misting Logic

The system automatically controls misting based on these conditions:

**Start Misting When:**
- Temperature > 95°F **AND**
- Humidity < 35%

**Stop Misting When:**
- Temperature < 95°F **OR**
- Humidity > 35% **OR**
- Maximum duration reached (10 minutes default)

**Safety Features:**
- 5-minute cooldown between cycles
- Emergency stop on system shutdown
- Manual pause/resume via web interface

## Configuration

All settings are configured via environment variables in `.env`:

```bash
# API Credentials (Required)
SWITCHBOT_TOKEN=your_switchbot_token
SWITCHBOT_SECRET=your_switchbot_secret  
RACHIO_API_TOKEN=your_rachio_token

# Device IDs (Required)
HUB2_DEVICE_ID=your_hub2_id
RACHIO_VALVE_ID=your_valve_id

# Thresholds (Optional - defaults shown)
TEMP_HIGH=95          # °F
TEMP_LOW=95           # °F  
HUMIDITY_LOW=35       # %
HUMIDITY_HIGH=35      # %

# Timing (Optional - defaults shown)
MISTER_DURATION=600   # seconds (10 minutes)
CHECK_INTERVAL=60     # seconds (1 minute)
COOLDOWN_SECONDS=300  # seconds (5 minutes)
```

## API Credentials Setup

### SwitchBot API
1. Open SwitchBot app (v6.14+)
2. Go to Profile → Preferences  
3. Copy Token and Secret

### Rachio API
1. Visit https://app.rach.io/

### Secure Credential Storage

**For Production (Docker Secrets - Recommended):**
```bash
# 1. Add credentials to .env file
# 2. Set up Docker secrets
./scripts/setup-secrets.sh

# 3. Deploy with secrets
docker-compose up -d

# 4. Verify secrets are loaded
docker-compose logs | grep "Loaded secret"
```

**For Development (.env file):**
```bash
# Just use .env file directly
cp .env.example .env
# Edit .env with your credentials
docker-compose up -d
```

Docker secrets provide better security by keeping credentials out of `docker inspect` output and process lists. See [secrets/README.md](secrets/README.md) for details.
2. Go to Account Settings
3. Click "GET API KEY"

### Find Device IDs

Use the diagnostic tool to find your device IDs:

```bash
# Find all available devices (SwitchBot Hub 2 and Rachio Smart Hose Timer)
python tools/find_devices.py
```

**Note:** `tools/setup_wizard.py` and `tools/verify_setup.py` are deprecated as they were designed for traditional Rachio controllers. This system only supports Rachio Smart Hose Timer.

## Run Modes

### Web Server (Recommended)
Full-featured web interface with REST API:
```bash
python api_server.py
```

### Standalone Controller  
Direct sensor monitoring without web UI:
```bash
python standalone_controller.py
```

## Web Interface

The web UI provides:

- **Real-time status** - Current temperature, humidity, and misting state
- **System controls** - Pause, resume, start, stop
- **Configuration display** - Current thresholds and timing
- **System stats** - Uptime, restart count, crash detection

## Production Deployment

See [README-Production.md](README-Production.md) for complete production deployment guide including:

- systemd service setup
- Backup/restore procedures  
- Monitoring and alerting
- Security considerations
- Maintenance procedures

## Development

### Local Development

```bash
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-web.txt

# Run API server
python api_server.py

# Run standalone controller (testing)
python standalone_controller.py
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SwitchBot     │    │     FastAPI      │    │     Rachio      │
│     Hub 2       │◄──►│   Web Server     │◄──►│ Smart Hose      │
│                 │    │                  │    │    Timer        │
│ • Temperature   │    │ • REST API       │    │ • Valve Control │
│ • Humidity      │    │ • Web UI         │    │ • Start/Stop    │
│ • Wireless      │    │ • State Manager  │    │ • Duration      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                       ┌──────────────────┐
                       │   Docker/State   │
                       │                  │
                       │ • Persistence    │
                       │ • Health Checks  │
                       │ • Auto Restart   │
                       └──────────────────┘
```

## Files Structure

```
server_shed_misters/
├── api_server.py              # FastAPI web server and API
├── standalone_controller.py   # Standalone controller
├── mister_controller.py       # API clients (SwitchBotAPI, SmartHoseTimerAPI) and data models
├── decision_engine.py        # Misting decision logic
├── state_manager.py          # State persistence
├── docker-compose.yml        # Docker development config
├── docker-compose.prod.yml   # Docker production config
├── Dockerfile               # Container image
├── requirements-web.txt     # Python dependencies
├── .env.example            # Environment template
├── scripts/
│   ├── deploy.sh          # Production deployment
│   ├── backup.sh          # Data backup
│   └── restore.sh         # Data restore
├── systemd/
│   └── mister-controller.service # systemd service
└── tools/
    └── find_devices.py    # Device discovery tool
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
docker-compose logs
journalctl -u mister-controller -f
```

**API connection issues:**
```bash
# Test credentials
python test_connections.py
python get_smart_valves.py
```

**Temperature readings wrong:**
- SwitchBot API returns Celsius, automatically converted to Fahrenheit
- Check device placement and calibration

**Misting not triggering:**
- Verify both temperature AND humidity thresholds are met
- Check cooldown period hasn't been triggered
- Ensure system is not paused

### Support

- 📖 [Production Guide](README-Production.md)
- 🐛 [Issues](https://github.com/damenknight/server-shed-misters/issues)
- 💬 [Discussions](https://github.com/damenknight/server-shed-misters/discussions)

---

**Built for reliable server shed climate control** 🏭❄️💨
