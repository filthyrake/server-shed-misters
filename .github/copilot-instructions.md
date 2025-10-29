# Copilot Instructions for Server Shed Misters

This file provides guidance to GitHub Copilot when working with code in this repository.

## Project Overview

This is a production-ready automated climate control system for server sheds that uses SwitchBot Hub 2 sensors and Rachio Smart Hose Timer valves. The system monitors temperature/humidity and automatically controls misting to maintain optimal conditions.

**Important Context**: This system controls physical hardware (water valves) and should include appropriate safety checks and error handling in all modifications.

## Development Workflow

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
python standalone_controller.py

# Docker development (auto-reload enabled)
docker-compose up -d

# Docker production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Testing and Diagnostics
The project uses integration testing rather than unit tests:
- `python tools/verify_setup.py` - Verify API credentials and connections
- `python tools/setup_wizard.py` - Interactive setup wizard
- `python tools/find_devices.py` - Find all available devices and IDs

**Note**: All diagnostic tools require real API credentials and are meant for development/debugging. There is no automated test suite - testing is manual and integration-focused.

## Architecture and Design Patterns

### Threading Architecture
The system uses a **threaded architecture** where the main FastAPI web server runs alongside a background controller thread:

1. **`api_server.py`**: FastAPI web server with embedded background controller thread
2. **`MisterControllerState`**: Global state manager that runs the sensor monitoring loop in a separate thread
3. **`state_manager.py`**: Handles persistence across restarts, crash detection, and pause/resume state
4. **`mister_controller.py`**: Core API wrappers and business logic for SwitchBot integration
5. **`standalone_controller.py`**: Contains `SmartHoseTimerAPI` class for Rachio integration

### API Integration Pattern
The project integrates with two different API architectures:
- **SwitchBot**: Traditional REST API at `api.switch-bot.com` with HMAC-SHA256 authentication
- **Rachio Smart Hose Timer**: Uses `cloud-rest.rach.io` endpoint with Bearer token authentication (different from traditional Rachio controllers)

### State Management
The system maintains persistent state in `./data/state.json` including:
- Pause/resume status (persists across restarts)
- Last mister start time (for cooldown calculations)
- Crash detection counters (distinguishes between graceful shutdowns and crashes)

## Critical Implementation Details

### Temperature Conversion
**CRITICAL**: SwitchBot API returns temperature in Celsius but the application logic works in Fahrenheit. The conversion happens in `SwitchBotAPI.get_hub2_data()` method. Always maintain this conversion when modifying temperature-related code.

### Misting Decision Logic
The system uses **AND/OR logic** for start/stop decisions:
- **Start**: Temperature > threshold **AND** Humidity < threshold
- **Stop**: Temperature < threshold **OR** Humidity > threshold **OR** max duration reached

### Safety Mechanisms
Always preserve these safety features when making changes:
- **Cooldown period**: Prevents rapid cycling (configurable, default 5 minutes)
- **Emergency stop**: Automatically stops misting on system shutdown
- **Pause functionality**: Completely disables decision logic while preserving sensor monitoring

## Configuration

All configuration is via environment variables (see `.env.example`). The system supports **auto-discovery** of device IDs if not provided:
- SwitchBot Hub 2 devices are auto-detected from the device list
- Rachio base stations and valves are discovered through API enumeration

Critical environment variables:
- `SWITCHBOT_TOKEN/SECRET`: Required for sensor access
- `RACHIO_API_TOKEN`: Required for valve control
- `HUB2_DEVICE_ID/RACHIO_VALVE_ID`: Can be auto-discovered but should be set for production
- Temperature/humidity thresholds and timing settings are all configurable

## Docker and Deployment

### Docker Configuration
- `docker-compose.yml`: Base configuration
- `docker-compose.override.yml`: Development overrides (hot reload, volume mounting)
- `docker-compose.prod.yml`: Production overrides (resource limits, optimized logging)

### State Persistence
Uses Docker named volume `mister-data` mounted at `/app/data` for state file persistence across container restarts.

### Production Deployment
```bash
# Deploy to server (requires root)
sudo scripts/deploy.sh

# Backup system state
sudo scripts/backup.sh

# Restore from backup
sudo scripts/restore.sh /path/to/backup.tar.gz
```

## Code Style and Conventions

- Use existing libraries and patterns - don't introduce new dependencies unless absolutely necessary
- Maintain consistency with existing code style (no specific linter configured)
- Error handling should be comprehensive since this controls physical hardware
- Logging should be informative for debugging production issues

## Production Considerations

The system is designed to run as a systemd service with Docker Compose, providing:
- Automatic restart on failure
- Proper logging integration
- Resource limits and health checks
- `/health` endpoint for health monitoring

## File Structure Reference

```
server_shed_misters/
├── api_server.py              # FastAPI web server and API
├── standalone_controller.py   # Standalone controller (with SmartHoseTimerAPI)
├── mister_controller.py       # Core controller logic and SwitchBot integration
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
    ├── verify_setup.py    # Test API connections
    ├── setup_wizard.py    # Interactive setup
    └── find_devices.py    # Device discovery
```

## Safety Guidelines

When working with this codebase:
1. Always test changes that affect misting logic with the diagnostic tools first
2. Never remove or bypass safety mechanisms (cooldown, emergency stop, pause)
3. Be cautious with state management changes - incorrect state can cause unexpected behavior
4. Always validate temperature conversions (Celsius ↔ Fahrenheit)
5. Consider the physical implications of code changes (water valve control)

## Additional Resources

- See `README.md` for user-facing documentation
- See `README-Production.md` for production deployment guide
- See `CLAUDE.md` for detailed technical notes (maintained for Claude.ai/code compatibility)
