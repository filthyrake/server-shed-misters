# API Security Features

This document describes the security features implemented for the Mister Controller API endpoints.

## Overview

The control endpoints (`/api/start`, `/api/stop`, `/api/pause`, `/api/resume`) have been enhanced with multiple layers of security to prevent:
- Hardware damage from valve cycling
- API quota exhaustion
- Race conditions and state corruption
- Denial of service attacks

## Security Features

### 1. Rate Limiting

All control endpoints are rate-limited to **5 requests per minute per client IP address**.

**Implementation:**
- Uses `slowapi` library with FastAPI integration
- Rate limit is enforced per remote IP address
- Returns HTTP 429 (Too Many Requests) when limit exceeded

**Example Response (Rate Limit Exceeded):**
```json
{
  "error": "Rate limit exceeded: 5 per 1 minute"
}
```

**Protected Endpoints:**
- `POST /api/start` - 5/minute
- `POST /api/stop` - 5/minute
- `POST /api/pause` - 5/minute
- `POST /api/resume` - 5/minute

### 2. State Validation

All state changes are protected with validation to prevent invalid operations.

**Features:**
- Thread-safe state changes using `threading.Lock`
- Validates state transitions before applying changes
- Prevents race conditions from concurrent requests

**Examples:**
```python
# Starting when already running
POST /api/start
→ {"success": false, "message": "Controller is already running"}

# Pausing when already paused
POST /api/pause
→ {"success": false, "message": "Controller is already paused"}

# Resuming when not paused
POST /api/resume
→ {"success": false, "message": "Controller is not paused"}
```

### 3. Thread Safety

All control operations use a mutex lock to prevent concurrent modifications.

**Implementation:**
```python
with self._state_lock:
    # State validation and modification
    # This ensures atomic state changes
```

**Protection Against:**
- Multiple concurrent start requests spawning multiple threads
- Race conditions between pause/resume/stop operations
- State corruption from simultaneous requests

### 4. Hardware Safety Delays

Enforces a minimum interval between valve operations to prevent hardware damage.

**Configuration:**
- `MIN_VALVE_ACTION_INTERVAL`: 30 seconds (default)
- Tracks timestamp of all valve operations
- Prevents rapid cycling that could damage the physical valve

**Implementation:**
```python
def _check_valve_action_safety(self) -> tuple[bool, str]:
    """Check if it's safe to perform a valve action (hardware safety delay)"""
    if self._last_valve_action_time is None:
        return True, "OK"
    
    elapsed = time.time() - self._last_valve_action_time
    if elapsed < self.MIN_VALVE_ACTION_INTERVAL:
        remaining = int(self.MIN_VALVE_ACTION_INTERVAL - elapsed)
        return False, f"Hardware safety: Wait {remaining}s before next valve action"
    
    return True, "OK"
```

**Emergency Override:**
The stop operation can override the safety delay if misting is currently active, to ensure immediate shutdown capability in emergencies.

### 5. Race Condition Prevention

Start operation includes additional checks to prevent thread spawning race conditions:

```python
def start(self):
    with self._state_lock:  # Thread-safe critical section
        if self.is_running:
            return False, "Controller is already running"
        
        # Check if a thread is already starting/running to prevent race conditions
        if self.controller_thread and self.controller_thread.is_alive():
            return False, "Controller thread is already active"
        
        # ... start the controller thread
```

This prevents the scenario where multiple start requests could spawn multiple controller threads.

### 6. Environment Variable Validation

All environment variables are validated and bounds-checked at startup to prevent:
- Application crashes from invalid configuration
- Hardware damage from extreme values
- API spam from inappropriate timing settings

**Implementation:**

Environment variables are parsed using safe helper functions (`safe_get_env_float` and `safe_get_env_int` from `env_utils.py`) that:

1. **Validate Format**: Non-numeric values are rejected and defaults are used
   ```python
   TEMP_HIGH=not_a_number  # ⚠️ Logs error, uses default 95°F
   ```

2. **Enforce Bounds**: Values outside safe ranges are automatically clamped
   ```python
   TEMP_HIGH=999           # ⚠️ Clamped to max 130°F
   MISTER_DURATION=86400   # ⚠️ Clamped to max 7200s (2 hours)
   COOLDOWN_SECONDS=0      # ⚠️ Clamped to min 60s
   CHECK_INTERVAL=1        # ⚠️ Clamped to min 10s
   ```

**Configuration Bounds:**

| Parameter | Minimum | Maximum | Reason |
|-----------|---------|---------|--------|
| Temperature | 32°F | 130°F | Prevent damage from extreme settings |
| Humidity | 0% | 100% | Valid percentage range |
| Mister Duration | 60s | 7200s | 1 minute to 2 hours (prevent over-watering) |
| Check Interval | 10s | 3600s | Prevent API spam |
| Cooldown | 60s | 86400s | Prevent rapid valve cycling |

**Protection Against:**
- **Hardware Damage**: Extreme mister duration values could flood equipment
- **Valve Cycling**: Zero or very low cooldown could damage physical valves
- **API Quota Exhaustion**: Very short check intervals could exhaust API quotas
- **Application Crashes**: Invalid input that would cause type conversion errors

All validation issues are logged at ERROR or WARNING level, making configuration problems easy to identify.

## Security Best Practices

### Credential Management

**Docker Secrets (Recommended for Production)**

The application uses Docker secrets to securely store API credentials:

```bash
# Set up secrets from .env file
./scripts/setup-secrets.sh

# Verify secrets are configured
ls -l secrets/
# Should show switchbot_token, switchbot_secret, rachio_api_token with 600 permissions
```

**Benefits:**
- ✅ Credentials NOT visible in `docker inspect` output
- ✅ Credentials NOT visible in process lists
- ✅ Credentials NOT logged in container metadata
- ✅ Secrets stored as files with OS-level permissions
- ✅ Secrets can be encrypted at rest

**Verification:**
```bash
# Check that credentials are NOT in docker inspect
docker inspect mister-controller | grep -i token
# Should show empty or placeholder values, not actual tokens

# Check that secrets are loaded correctly
docker-compose logs | grep "Loaded secret"
# Should show: "Loaded secret 'switchbot_token' from Docker secrets"
```

For detailed setup instructions, see [secrets/README.md](secrets/README.md).

### Network Security
While the API includes rate limiting and state validation, it should still be protected at the network level:

1. **Firewall**: Restrict access to trusted IP addresses
2. **VPN**: Access the controller through a VPN
3. **Reverse Proxy**: Use nginx/traefik with additional security headers
4. **HTTPS**: Use TLS certificates for encrypted communication (via reverse proxy)

### Monitoring

Monitor for suspicious activity:
- Multiple 429 (rate limit) responses
- Repeated failed state transitions
- Valve action safety warnings in logs

### Example Nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name mister-controller.local;

    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # IP whitelist
    allow 192.168.1.0/24;
    deny all;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Testing Security Features

### Rate Limiting Test

```bash
# This should succeed 5 times, then fail with 429
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/pause
  echo ""
done
```

### State Validation Test

```bash
# Start the controller
curl -X POST http://localhost:8000/api/start

# Try to start again (should fail)
curl -X POST http://localhost:8000/api/start
# Expected: {"success": false, "message": "Controller is already running"}
```

### Hardware Safety Test

The hardware safety delay is enforced automatically in the controller loop. You can observe it in the logs when valve actions occur close together.

## Configuration

### Environment Variables

No additional environment variables are required for the security features. The rate limits and safety delays are configured with sensible defaults:

- Rate Limit: 5 requests/minute (hardcoded in `api_server.py`)
- Hardware Safety Interval: 30 seconds (configurable via `MIN_VALVE_ACTION_INTERVAL`)

### Adjusting Rate Limits

To modify rate limits, edit `api_server.py`:

```python
@app.post("/api/pause")
@limiter.limit("10/minute")  # Change from 5 to 10
async def pause_controller(request: Request) -> ControlResponse:
    ...
```

### Adjusting Hardware Safety Interval

To modify the minimum valve action interval, edit `api_server.py`:

```python
class MisterControllerState:
    def __init__(self):
        ...
        self.MIN_VALVE_ACTION_INTERVAL = 60  # Change from 30 to 60 seconds
```

## Impact on Normal Operation

These security features are designed to be transparent during normal operation:

- **Rate Limiting**: Normal users will never hit the 5/minute limit
- **State Validation**: Prevents errors, doesn't restrict valid operations  
- **Hardware Safety**: The 30-second minimum is less than the default cooldown (300 seconds)
- **Thread Safety**: Adds negligible overhead to API response times

## Threat Model

### Mitigated Threats

1. **Valve Hammering (High Severity)**
   - Attack: Rapid start/stop cycling damages physical valve
   - Mitigation: Hardware safety delay + rate limiting

2. **API Quota Exhaustion (Medium Severity)**
   - Attack: Excessive requests exhaust SwitchBot/Rachio API quotas
   - Mitigation: Rate limiting

3. **Denial of Service (Medium Severity)**
   - Attack: Pause/resume spam prevents normal operation
   - Mitigation: Rate limiting + state validation

4. **Race Conditions (Low Severity)**
   - Attack: Concurrent requests cause unpredictable behavior
   - Mitigation: Thread safety locks + state validation

### Remaining Risks

1. **Distributed DoS**: Rate limiting is per-IP, could be bypassed with multiple IPs
   - Recommendation: Network-level protection (firewall, fail2ban)

2. **Authenticated Attackers**: No authentication/authorization implemented
   - Recommendation: Add API key authentication or use reverse proxy auth

3. **Physical Access**: Someone with physical access could manipulate hardware directly
   - Recommendation: Physical security measures

## Changelog

### Version 1.2.0 (Current)
- Added environment variable validation with bounds checking
- Added safe parsing functions to prevent application crashes from invalid input
- Added automatic clamping of extreme values to safe ranges
- Improved startup robustness with comprehensive error handling

### Version 1.1.0
- Added rate limiting (5 requests/minute per endpoint)
- Added state validation for all control operations
- Added hardware safety delays (30-second minimum between valve operations)
- Added thread safety locks for state modifications
- Added race condition prevention for concurrent starts

### Version 1.0.0 (Original)
- Basic control endpoints without validation
