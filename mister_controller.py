#!/usr/bin/env python3

import os
import time
import json
import hmac
import hashlib
import base64
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MisterAction(Enum):
    NONE = "none"
    START = "start"
    STOP = "stop"


@dataclass
class SensorReading:
    temperature: float
    humidity: float
    timestamp: datetime


@dataclass
class MisterConfig:
    temperature_threshold_high: float = 95.0
    temperature_threshold_low: float = 95.0
    humidity_threshold_low: float = 35.0
    humidity_threshold_high: float = 35.0
    mister_duration_seconds: int = 600
    check_interval_seconds: int = 60
    cooldown_seconds: int = 300


def _create_retry_session(allowed_methods: List[str]) -> requests.Session:
    """
    Create a requests Session with retry strategy and exponential backoff.
    
    Retry behavior: With total=3 and backoff_factor=2, requests will be retried
    up to 3 times with delays of 2s, 4s, and 8s between attempts (exponential).
    This means a failing request could take up to 14 seconds before giving up.
    
    For systems controlling physical hardware (water valves), this ensures
    transient network issues are handled gracefully while avoiding indefinite hangs.
    
    Args:
        allowed_methods: HTTP methods to retry (e.g., ["GET", "POST"])
    
    Returns:
        Configured requests.Session with retry logic
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=allowed_methods
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking calls."""
    pass


class CircuitBreaker:
    """
    Simple circuit breaker for API calls to prevent repeated failures.
    
    States:
    - closed: Normal operation, requests allowed
    - open: Circuit is open due to failures, requests blocked
    - half_open: Testing if service has recovered
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 300):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit (default: 5)
            timeout_seconds: Seconds to wait before attempting recovery (default: 300)
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
        self._lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func if successful
            
        Raises:
            CircuitBreakerOpenError: If circuit is open or half-open
            Exception: If function execution fails
        """
        # Check state and transition if needed (thread-safe)
        with self._lock:
            if self.state == "open":
                if self.last_failure_time and time.time() - self.last_failure_time > self.timeout_seconds:
                    self.state = "half_open"
                    logger.info("Circuit breaker entering half-open state, attempting recovery")
                    # Allow this thread to proceed for testing
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker is open (failures: {self.failures})")
            elif self.state == "half_open":
                # Only allow one test request in half-open state
                raise CircuitBreakerOpenError(f"Circuit breaker is half-open, test in progress (failures: {self.failures})")
            # If closed, proceed as normal
        
        try:
            result = func(*args, **kwargs)
            
            with self._lock:
                if self.state == "half_open":
                    self.state = "closed"
                    self.failures = 0
                    logger.info("Circuit breaker closed - service recovered")
                elif self.state == "closed":
                    # Reset failure counter on successful call
                    self.failures = 0
            
            return result
        except Exception as e:
            with self._lock:
                self.failures += 1
                self.last_failure_time = time.time()
                
                if self.failures >= self.failure_threshold:
                    if self.state != "open":
                        self.state = "open"
                        logger.error(f"Circuit breaker opened after {self.failures} failures")
            raise


class RateLimitedAPIMixin:
    """Mixin class providing thread-safe rate limiting for API calls."""
    
    def _init_rate_limiting(self, min_request_interval: float = 0.5):
        """
        Initialize rate limiting attributes.
        
        Args:
            min_request_interval: Minimum seconds between API calls (default: 0.5)
        """
        # Initialize to allow first request immediately
        self._last_request_time = time.time() - min_request_interval
        self._min_request_interval = min_request_interval
        self._rate_limit_lock = threading.Lock()
    
    def _rate_limit(self):
        """Enforce minimum interval between API calls (thread-safe)."""
        with self._rate_limit_lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()


class SwitchBotAPI(RateLimitedAPIMixin):
    def __init__(self, token: str, secret: str):
        self.token = token
        self.secret = secret
        self.base_url = "https://api.switch-bot.com"
        self.api_version = "v1.1"
        
        # Rate limiting - SwitchBot allows 10,000 calls/day (~6.94 calls/minute)
        # Using 500ms interval allows 120 calls/minute, well under daily limit
        # At CHECK_INTERVAL=60s, actual rate is ~1 call/minute in normal operation
        self._init_rate_limiting(min_request_interval=0.5)
        
        # Retry strategy with exponential backoff
        self.session = _create_retry_session(allowed_methods=["GET", "POST"])
        
    def _generate_signature(self) -> Tuple[str, str, str]:
        nonce = ""
        t = str(int(round(time.time() * 1000)))
        string_to_sign = f"{self.token}{t}{nonce}"
        
        secret_bytes = bytes(self.secret, 'utf-8')
        string_to_sign_bytes = bytes(string_to_sign, 'utf-8')
        
        sign = base64.b64encode(
            hmac.new(secret_bytes, msg=string_to_sign_bytes, digestmod=hashlib.sha256).digest()
        ).decode('utf-8')
        
        return sign, t, nonce
    
    def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Optional[Dict]:
        # Apply rate limiting
        self._rate_limit()
        
        sign, t, nonce = self._generate_signature()
        
        headers = {
            "Authorization": self.token,
            "sign": sign,
            "t": t,
            "nonce": nonce,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/{self.api_version}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, timeout=(10, 30))
            else:
                response = self.session.post(url, headers=headers, json=data, timeout=(10, 30))
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"SwitchBot API request failed: {e}")
            return None
    
    def get_devices(self) -> Optional[List[Dict]]:
        result = self._make_request("/devices")
        if result and result.get("statusCode") == 100:
            return result.get("body", {}).get("deviceList", [])
        return None
    
    def get_device_status(self, device_id: str) -> Optional[Dict]:
        result = self._make_request(f"/devices/{device_id}/status")
        if result and result.get("statusCode") == 100:
            return result.get("body")
        return None
    
    def get_hub2_data(self, device_id: str) -> Optional[SensorReading]:
        status = self.get_device_status(device_id)
        if status:
            try:
                temp_celsius = float(status.get("temperature", 0))
                temp_fahrenheit = (temp_celsius * 9/5) + 32
                
                return SensorReading(
                    temperature=temp_fahrenheit,
                    humidity=float(status.get("humidity", 0)),
                    timestamp=datetime.now(ZoneInfo("localtime"))
                )
            except (KeyError, ValueError) as e:
                logger.error(f"Failed to parse Hub2 data: {e}")
        return None


class SmartHoseTimerAPI(RateLimitedAPIMixin):
    """
    API client for Rachio Smart Hose Timer.
    
    NOTE: This is different from traditional Rachio controllers (which use api.rach.io).
    The Smart Hose Timer uses a different API endpoint and authentication model.
    """
    
    def __init__(self, api_token: str, circuit_breaker_enabled: bool = True,
                 failure_threshold: int = 5, timeout_seconds: int = 300):
        """
        Initialize Smart Hose Timer API client.
        
        Args:
            api_token: Rachio API token for authentication
            circuit_breaker_enabled: Enable circuit breaker protection (default: True)
            failure_threshold: Number of failures before opening circuit (default: 5)
            timeout_seconds: Seconds to wait before retry after circuit open (default: 300)
        """
        self.api_token = api_token
        self.base_url = "https://cloud-rest.rach.io"
        
        # Rate limiting
        self._init_rate_limiting(min_request_interval=0.5)
        
        # Retry strategy with exponential backoff
        self.session = _create_retry_session(allowed_methods=["GET", "POST", "PUT"])
        
        # Circuit breaker for hardware failure protection
        self.circuit_breaker_enabled = circuit_breaker_enabled
        if circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=failure_threshold,
                timeout_seconds=timeout_seconds
            )
        else:
            self.circuit_breaker = None
        
    def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Optional[Dict]:
        # Apply rate limiting
        self._rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, timeout=(10, 30))
            elif method == "PUT":
                response = self.session.put(url, headers=headers, json=data, timeout=(10, 30))
            else:
                response = self.session.post(url, headers=headers, json=data, timeout=(10, 30))
            
            if response.status_code == 200:
                return response.json() if response.content else {"success": True}
            elif response.status_code == 204:
                return {"success": True}
            else:
                logger.error(f"Smart Hose Timer API error {response.status_code}: {response.text}")
                return None
        except requests.RequestException as e:
            logger.error(f"Smart Hose Timer API exception: {e}")
            return None
    
    def start_watering(self, valve_id: str, duration_seconds: int) -> bool:
        """
        Start watering for the specified duration.
        
        Protected by circuit breaker to prevent repeated failures.
        
        Args:
            valve_id: ID of the valve to start
            duration_seconds: How long to water in seconds
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting valve {valve_id} for {duration_seconds} seconds")
        
        if self.circuit_breaker_enabled and self.circuit_breaker:
            try:
                result = self.circuit_breaker.call(
                    self._start_watering_impl, valve_id, duration_seconds
                )
                return result
            except Exception as e:
                logger.error(f"Circuit breaker prevented start_watering call: {e}")
                return False
        else:
            return self._start_watering_impl(valve_id, duration_seconds)
    
    def _start_watering_impl(self, valve_id: str, duration_seconds: int) -> bool:
        """Internal implementation of start_watering."""
        result = self._make_request("/valve/startWatering", "PUT", {
            "valveId": valve_id,
            "durationSeconds": duration_seconds
        })
        
        if result is None:
            if self.circuit_breaker_enabled:
                # When circuit breaker is enabled, raise to trigger circuit breaker logic
                raise Exception(f"start_watering API request failed for valve {valve_id} (duration: {duration_seconds}s)")
            else:
                # When circuit breaker is disabled, return False for backward compatibility
                return False
        
        return True
    
    def stop_watering(self, valve_id: str) -> bool:
        """
        Stop watering.
        
        Protected by circuit breaker to prevent repeated failures.
        
        Args:
            valve_id: ID of the valve to stop
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Stopping valve {valve_id}")
        
        if self.circuit_breaker_enabled and self.circuit_breaker:
            try:
                result = self.circuit_breaker.call(
                    self._stop_watering_impl, valve_id
                )
                return result
            except Exception as e:
                logger.error(f"Circuit breaker prevented stop_watering call: {e}")
                return False
        else:
            return self._stop_watering_impl(valve_id)
    
    def _stop_watering_impl(self, valve_id: str) -> bool:
        """Internal implementation of stop_watering."""
        result = self._make_request("/valve/stopWatering", "PUT", {
            "valveId": valve_id
        })
        
        if result is None:
            if self.circuit_breaker_enabled:
                # When circuit breaker is enabled, raise to trigger circuit breaker logic
                raise Exception(f"stop_watering API request failed for valve {valve_id}")
            else:
                # When circuit breaker is disabled, return False for backward compatibility
                return False
        
        return True
    
    def get_valve_status(self, valve_id: str) -> Optional[Dict]:
        """Get valve status"""
        # This would require finding the right endpoint for valve status
        # For now, we'll rely on our own state tracking
        return {}