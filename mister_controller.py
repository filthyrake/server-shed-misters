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
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://cloud-rest.rach.io"
        
        # Rate limiting
        self._init_rate_limiting(min_request_interval=0.5)
        
        # Retry strategy with exponential backoff
        self.session = _create_retry_session(allowed_methods=["GET", "POST", "PUT"])
        
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
        """Start watering for the specified duration"""
        logger.info(f"Starting valve {valve_id} for {duration_seconds} seconds")
        
        result = self._make_request("/valve/startWatering", "PUT", {
            "valveId": valve_id,
            "durationSeconds": duration_seconds
        })
        
        return result is not None
    
    def stop_watering(self, valve_id: str) -> bool:
        """Stop watering"""
        logger.info(f"Stopping valve {valve_id}")
        
        result = self._make_request("/valve/stopWatering", "PUT", {
            "valveId": valve_id
        })
        
        return result is not None
    
    def get_valve_status(self, valve_id: str) -> Optional[Dict]:
        """Get valve status"""
        # This would require finding the right endpoint for valve status
        # For now, we'll rely on our own state tracking
        return {}