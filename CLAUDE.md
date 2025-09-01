# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready automated climate control system for server sheds that uses SwitchBot Hub 2 sensors and Rachio Smart Hose Timer valves. The system monitors temperature/humidity and automatically controls misting to maintain optimal conditions.

## Development Commands

### Environment Setup
```bash
# Local development
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-web.txt
cp .env.example .env  # Then edit with real credentials
```

### Running the Application
```bash
# Development web server (with hot reload)
python api_server.py

# Standalone controller (direct sensor monitoring without web UI)
python final_mister_controller.py

# Docker development (auto-reload enabled)
docker-compose up -d

# Docker production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Testing and Debugging
```bash
# Test API connections and find device IDs
python test_connections.py      # SwitchBot devices
python get_smart_valves.py      # Rachio Smart Hose Timer
python debug_switchbot_temp.py  # Temperature conversion debugging

# Test individual API endpoints
python find_rachio_devices.py   # Comprehensive Rachio discovery
```

### Production Deployment
```bash
# Deploy to server (requires root)
sudo scripts/deploy.sh

# Backup system state
sudo scripts/backup.sh

# Restore from backup
sudo scripts/restore.sh /path/to/backup.tar.gz
```

## Architecture Overview

### Core Components
The system uses a **threaded architecture** where the main FastAPI web server runs alongside a background controller thread:

1. **`api_server.py`**: FastAPI web server with embedded background controller thread
2. **`MisterControllerState`**: Global state manager that runs the sensor monitoring loop in a separate thread
3. **`state_manager.py`**: Handles persistence across restarts, crash detection, and pause/resume state
4. **`mister_controller.py`**: Core API wrappers and business logic for SwitchBot/Rachio integration

### API Integration Pattern
The project integrates with two different API architectures:
- **SwitchBot**: Traditional REST API at `api.switch-bot.com` with HMAC-SHA256 authentication
- **Rachio Smart Hose Timer**: Uses `cloud-rest.rach.io` endpoint (different from traditional Rachio controllers)

### State Management
The system maintains persistent state in `./data/state.json` including:
- Pause/resume status (persists across restarts)
- Last mister start time (for cooldown calculations)
- Crash detection counters (distinguishes between graceful shutdowns and crashes)

### Temperature Conversion
**Critical**: SwitchBot API returns temperature in Celsius but the application logic works in Fahrenheit. The conversion happens in `SwitchBotAPI.get_hub2_data()` method.

## Key Business Logic

### Misting Decision Logic
The system uses **AND/OR logic** for start/stop decisions:
- **Start**: Temperature > threshold **AND** Humidity < threshold
- **Stop**: Temperature < threshold **OR** Humidity > threshold **OR** max duration reached

### Safety Mechanisms
- **Cooldown period**: Prevents rapid cycling (configurable, default 5 minutes)
- **Emergency stop**: Automatically stops misting on system shutdown
- **Pause functionality**: Completely disables decision logic while preserving sensor monitoring

## Environment Configuration

All configuration is via environment variables. The system supports **auto-discovery** of device IDs if not provided:
- SwitchBot Hub 2 devices are auto-detected from the device list
- Rachio base stations and valves are discovered through API enumeration

Critical environment variables:
- `SWITCHBOT_TOKEN/SECRET`: Required for sensor access
- `RACHIO_API_TOKEN`: Required for valve control
- `HUB2_DEVICE_ID/RACHIO_VALVE_ID`: Can be auto-discovered but should be set for production

## Docker Architecture

### Multi-stage Configuration
- `docker-compose.yml`: Base configuration
- `docker-compose.override.yml`: Development overrides (hot reload, volume mounting)
- `docker-compose.prod.yml`: Production overrides (resource limits, optimized logging)

### State Persistence
Uses Docker named volume `mister-data` mounted at `/app/data` for state file persistence across container restarts.

## Testing Strategy

The project includes **integration testing tools** rather than unit tests:
- Each `test_*.py` file tests specific API integrations or discovery mechanisms
- Tests require real API credentials and are meant for development/debugging
- No automated test suite - testing is manual and integration-focused

## Production Considerations

### Service Management
The system is designed to run as a systemd service with Docker Compose, providing:
- Automatic restart on failure
- Proper logging integration
- Resource limits and health checks

### Monitoring
Built-in monitoring through:
- `/health` endpoint for health checks
- State persistence tracks crash vs. graceful shutdown
- Comprehensive logging with rotation

When modifying this system, be aware that it controls physical hardware (water valves) and should include appropriate safety checks and error handling.