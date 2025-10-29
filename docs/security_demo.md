# Security Features Demonstration

This document demonstrates the security features implemented for the API control endpoints.

## Prerequisites

Start the server with valid API credentials:
```bash
python api_server.py
```

## Demonstration Scripts

### 1. Rate Limiting Demo

This script demonstrates that the API rejects requests after the rate limit is exceeded:

```bash
#!/bin/bash
# rate_limit_test.sh
echo "Testing rate limiting (5 requests/minute limit)..."
echo "Making 7 rapid requests to /api/pause..."
echo ""

for i in {1..7}; do
  echo "Request $i:"
  curl -X POST http://localhost:8000/api/pause -s | jq -r '.'
  echo ""
  sleep 0.5
done

echo "Notice: Requests 6+ should return rate limit errors (HTTP 429)"
```

**Expected Output:**
```
Request 1-5: {"success": true/false, "message": "...", "new_status": "..."}
Request 6-7: {"error": "Rate limit exceeded: 5 per 1 minute"}
```

### 2. State Validation Demo

This script demonstrates that invalid state transitions are rejected:

```bash
#!/bin/bash
# state_validation_test.sh
echo "Testing state validation..."
echo ""

# Test 1: Try to pause when stopped
echo "Test 1: Pause when controller is stopped (should fail)"
curl -X POST http://localhost:8000/api/pause -s | jq -r '.success, .message'
echo ""

# Test 2: Start controller
echo "Test 2: Start controller (should succeed)"
curl -X POST http://localhost:8000/api/start -s | jq -r '.success, .message'
sleep 1
echo ""

# Test 3: Try to start again
echo "Test 3: Start when already running (should fail)"
curl -X POST http://localhost:8000/api/start -s | jq -r '.success, .message'
echo ""

# Test 4: Pause controller
echo "Test 4: Pause controller (should succeed)"
curl -X POST http://localhost:8000/api/pause -s | jq -r '.success, .message'
sleep 1
echo ""

# Test 5: Try to pause again
echo "Test 5: Pause when already paused (should fail)"
curl -X POST http://localhost:8000/api/pause -s | jq -r '.success, .message'
echo ""

# Clean up
echo "Cleanup: Resume controller"
curl -X POST http://localhost:8000/api/resume -s | jq -r '.success, .message'
```

**Expected Output:**
```
Test 1: false, "Controller is not running"
Test 2: true, "Controller started successfully"
Test 3: false, "Controller is already running"
Test 4: true, "Controller paused"
Test 5: false, "Controller is already paused"
```

### 3. Concurrent Request Demo

This script demonstrates protection against race conditions:

```bash
#!/bin/bash
# concurrent_request_test.sh
echo "Testing concurrent request handling..."
echo ""

# Stop controller first
curl -X POST http://localhost:8000/api/stop -s > /dev/null 2>&1
sleep 1

# Launch 5 concurrent start requests
echo "Launching 5 concurrent start requests..."
for i in {1..5}; do
  (
    response=$(curl -X POST http://localhost:8000/api/start -s)
    success=$(echo $response | jq -r '.success')
    message=$(echo $response | jq -r '.message')
    echo "Request $i: success=$success, message=$message"
  ) &
done

wait
echo ""
echo "Only one should succeed, others should be rejected with 'already running' or 'thread already active'"
```

### 4. Hardware Safety Demo

The hardware safety delay is enforced automatically. To observe it:

```python
#!/usr/bin/env python3
# hardware_safety_demo.py
import time
import requests

BASE_URL = "http://localhost:8000"

print("Hardware Safety Delay Demonstration")
print("=" * 50)
print()

# This would require manual triggering of valve actions
# The 30-second safety delay prevents rapid valve cycling

print("Note: The hardware safety delay (30 seconds) is enforced")
print("automatically in the controller loop between valve actions.")
print()
print("You can observe it in action by:")
print("1. Monitoring the server logs")
print("2. Watching for valve start/stop events")
print("3. Noting that valve actions are spaced at least 30 seconds apart")
print()
print("The safety delay prevents scenarios like:")
print("  Time 0s: Start misting")
print("  Time 5s: Stop misting (allowed)")
print("  Time 10s: Start misting (BLOCKED - only 10s elapsed)")
print("  Time 35s: Start misting (allowed - 30s elapsed since stop)")
```

## Integration Test

A complete integration test that exercises all security features:

```python
#!/usr/bin/env python3
# security_integration_test.py
import time
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8000"

def test_rate_limiting():
    """Test that rate limiting works"""
    print("\n=== Rate Limiting Test ===")
    success_count = 0
    rate_limit_count = 0
    
    for i in range(7):
        r = requests.post(f"{BASE_URL}/api/pause")
        if r.status_code == 200:
            success_count += 1
        elif r.status_code == 429:
            rate_limit_count += 1
        time.sleep(0.1)
    
    print(f"Success: {success_count}, Rate Limited: {rate_limit_count}")
    assert rate_limit_count > 0, "Rate limiting should have triggered"
    print("✓ Rate limiting working")

def test_state_validation():
    """Test that invalid state transitions are rejected"""
    print("\n=== State Validation Test ===")
    
    # Stop first
    requests.post(f"{BASE_URL}/api/stop")
    time.sleep(1)
    
    # Try to pause when stopped
    r = requests.post(f"{BASE_URL}/api/pause")
    data = r.json()
    assert not data['success'], "Should not be able to pause when stopped"
    print("✓ Cannot pause when stopped")
    
    # Start controller
    r = requests.post(f"{BASE_URL}/api/start")
    time.sleep(0.5)
    
    # Try to start again
    r = requests.post(f"{BASE_URL}/api/start")
    data = r.json()
    assert not data['success'], "Should not be able to start when already running"
    print("✓ Cannot start when already running")

def test_concurrent_safety():
    """Test that concurrent requests are handled safely"""
    print("\n=== Concurrent Request Test ===")
    
    # Stop first
    requests.post(f"{BASE_URL}/api/stop")
    time.sleep(1)
    
    # Launch concurrent start requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(requests.post, f"{BASE_URL}/api/start") 
                  for _ in range(5)]
        results = [f.result().json() for f in futures]
    
    success_count = sum(1 for r in results if r['success'])
    assert success_count == 1, "Only one concurrent start should succeed"
    print(f"✓ Only {success_count} of 5 concurrent starts succeeded")

if __name__ == "__main__":
    print("Security Integration Test Suite")
    print("=" * 50)
    
    try:
        test_state_validation()
        test_concurrent_safety()
        test_rate_limiting()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
```

## Monitoring Security Events

View security-related log messages:

```bash
# Watch for rate limiting events
journalctl -u mister-controller -f | grep -i "rate limit"

# Watch for state validation failures
journalctl -u mister-controller -f | grep -i "already"

# Watch for hardware safety delays
journalctl -u mister-controller -f | grep -i "hardware safety"
```

## Security Metrics

Monitor these metrics to detect potential security issues:

1. **Rate limit hits**: Count of 429 responses
   - Normal: 0-5 per day
   - Suspicious: >10 per hour

2. **State validation failures**: Count of "already running/paused" errors
   - Normal: Occasional (user error)
   - Suspicious: Repeated from same IP

3. **Hardware safety delays**: Count of valve action blocks
   - Normal: 0 (shouldn't happen with proper cooldown)
   - Suspicious: Frequent occurrences suggest rapid cycling attempts

## Production Testing

When deploying to production:

1. **Verify rate limiting works**
   ```bash
   ./rate_limit_test.sh
   ```

2. **Verify state validation works**
   ```bash
   ./state_validation_test.sh
   ```

3. **Monitor logs for security events**
   ```bash
   tail -f /var/log/mister-controller.log | grep -E "(rate limit|already|hardware safety)"
   ```

4. **Test emergency stop**
   - Verify stop works even during hardware safety delay
   - Confirm valve actually stops

## Troubleshooting

### Rate Limit Too Restrictive

If legitimate users hit rate limits:
- Increase the rate limit in `api_server.py`
- Consider per-user rate limiting instead of per-IP
- Add rate limit headers to help clients back off

### False Positive State Errors

If you see unexpected "already running" errors:
- Check for slow network causing request retries
- Verify no duplicate button clicks in UI
- Review application logs for timing issues

### Hardware Safety False Alarms

If valve actions are blocked unexpectedly:
- Check if cooldown period (300s) is less than safety interval (30s)
- Review valve action timestamps in logs
- Verify controller loop timing is correct
