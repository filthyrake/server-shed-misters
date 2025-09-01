#!/usr/bin/env python3

import os
import time
import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

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


class SwitchBotAPI:
    def __init__(self, token: str, secret: str):
        self.token = token
        self.secret = secret
        self.base_url = "https://api.switch-bot.com"
        self.api_version = "v1.1"
        
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
                response = requests.get(url, headers=headers)
            else:
                response = requests.post(url, headers=headers, json=data)
            
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
                    timestamp=datetime.now()
                )
            except (KeyError, ValueError) as e:
                logger.error(f"Failed to parse Hub2 data: {e}")
        return None


class RachioAPI:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.rach.io/1/public"
        
    def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Optional[Dict]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            else:
                response = requests.post(url, headers=headers, json=data)
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Rachio API request failed: {e}")
            return None
    
    def get_person_info(self) -> Optional[Dict]:
        return self._make_request("/person/info")
    
    def get_person_id(self) -> Optional[str]:
        info = self.get_person_info()
        if info:
            return info.get("id")
        return None
    
    def get_devices(self, person_id: str) -> Optional[List[Dict]]:
        result = self._make_request(f"/person/{person_id}")
        if result:
            return result.get("devices", [])
        return None
    
    def start_zone(self, zone_id: str, duration: int) -> bool:
        data = {
            "id": zone_id,
            "duration": duration
        }
        result = self._make_request("/zone/start", method="PUT", data=data)
        return result is not None
    
    def stop_watering(self, device_id: str) -> bool:
        data = {
            "id": device_id
        }
        result = self._make_request("/device/stop_water", method="PUT", data=data)
        return result is not None


class MisterController:
    def __init__(self, switchbot_api: SwitchBotAPI, rachio_api: RachioAPI, 
                 hub2_device_id: str, rachio_zone_id: str, rachio_device_id: str,
                 config: MisterConfig):
        self.switchbot = switchbot_api
        self.rachio = rachio_api
        self.hub2_device_id = hub2_device_id
        self.rachio_zone_id = rachio_zone_id
        self.rachio_device_id = rachio_device_id
        self.config = config
        self.last_mister_start = None
        self.is_misting = False
        
    def should_start_mister(self, reading: SensorReading) -> bool:
        if self.is_misting:
            return False
            
        if self.last_mister_start:
            time_since_last = (datetime.now() - self.last_mister_start).total_seconds()
            if time_since_last < self.config.cooldown_seconds:
                logger.debug(f"In cooldown period. {self.config.cooldown_seconds - time_since_last:.0f} seconds remaining")
                return False
        
        temp_too_high = reading.temperature > self.config.temperature_threshold_high
        humidity_too_low = reading.humidity < self.config.humidity_threshold_low
        
        return temp_too_high and humidity_too_low
    
    def should_stop_mister(self, reading: SensorReading) -> bool:
        if not self.is_misting:
            return False
            
        temp_ok = reading.temperature < self.config.temperature_threshold_low
        humidity_ok = reading.humidity > self.config.humidity_threshold_high
        
        if self.last_mister_start:
            time_running = (datetime.now() - self.last_mister_start).total_seconds()
            max_duration_reached = time_running >= self.config.mister_duration_seconds
            
            return (temp_ok or humidity_ok) or max_duration_reached
        
        return False
    
    def start_mister(self) -> bool:
        logger.info(f"Starting mister for {self.config.mister_duration_seconds} seconds")
        success = self.rachio.start_zone(self.rachio_zone_id, self.config.mister_duration_seconds)
        if success:
            self.is_misting = True
            self.last_mister_start = datetime.now()
            logger.info("Mister started successfully")
        else:
            logger.error("Failed to start mister")
        return success
    
    def stop_mister(self) -> bool:
        logger.info("Stopping mister")
        success = self.rachio.stop_watering(self.rachio_device_id)
        if success:
            self.is_misting = False
            logger.info("Mister stopped successfully")
        else:
            logger.error("Failed to stop mister")
        return success
    
    def get_sensor_reading(self) -> Optional[SensorReading]:
        return self.switchbot.get_hub2_data(self.hub2_device_id)
    
    def process_reading(self, reading: SensorReading) -> MisterAction:
        logger.info(f"Sensor reading - Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
        
        if self.should_start_mister(reading):
            if self.start_mister():
                return MisterAction.START
        elif self.should_stop_mister(reading):
            if self.stop_mister():
                return MisterAction.STOP
        
        return MisterAction.NONE
    
    def run(self):
        logger.info("Starting Mister Controller")
        logger.info(f"Configuration: {self.config}")
        
        while True:
            try:
                reading = self.get_sensor_reading()
                if reading:
                    action = self.process_reading(reading)
                    if action != MisterAction.NONE:
                        logger.info(f"Action taken: {action.value}")
                else:
                    logger.warning("Failed to get sensor reading")
                
                time.sleep(self.config.check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Shutting down Mister Controller")
                if self.is_misting:
                    self.stop_mister()
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(self.config.check_interval_seconds)


def main():
    load_dotenv()
    
    switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
    switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
    rachio_token = os.environ.get("RACHIO_API_TOKEN")
    hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
    rachio_zone_id = os.environ.get("RACHIO_ZONE_ID")
    rachio_device_id = os.environ.get("RACHIO_DEVICE_ID")
    
    if not all([switchbot_token, switchbot_secret, rachio_token]):
        logger.error("Missing required environment variables")
        logger.error("Required: SWITCHBOT_TOKEN, SWITCHBOT_SECRET, RACHIO_API_TOKEN")
        logger.error("Optional: HUB2_DEVICE_ID, RACHIO_ZONE_ID, RACHIO_DEVICE_ID")
        return
    
    switchbot_api = SwitchBotAPI(switchbot_token, switchbot_secret)
    rachio_api = RachioAPI(rachio_token)
    
    if not hub2_device_id:
        logger.info("HUB2_DEVICE_ID not set, fetching devices...")
        devices = switchbot_api.get_devices()
        if devices:
            hub2_devices = [d for d in devices if d.get("deviceType") == "Hub 2"]
            if hub2_devices:
                hub2_device_id = hub2_devices[0]["deviceId"]
                logger.info(f"Found Hub 2 device: {hub2_device_id}")
            else:
                logger.error("No Hub 2 devices found")
                return
    
    if not rachio_zone_id or not rachio_device_id:
        logger.info("Fetching Rachio devices...")
        person_id = rachio_api.get_person_id()
        if person_id:
            devices = rachio_api.get_devices(person_id)
            if devices and len(devices) > 0:
                rachio_device_id = devices[0]["id"]
                zones = devices[0].get("zones", [])
                if zones:
                    enabled_zones = [z for z in zones if z.get("enabled")]
                    if enabled_zones:
                        rachio_zone_id = enabled_zones[0]["id"]
                        logger.info(f"Using zone: {enabled_zones[0].get('name', rachio_zone_id)}")
    
    if not all([hub2_device_id, rachio_zone_id, rachio_device_id]):
        logger.error("Could not determine all required device IDs")
        return
    
    config = MisterConfig(
        temperature_threshold_high=float(os.environ.get("TEMP_HIGH", 95)),
        temperature_threshold_low=float(os.environ.get("TEMP_LOW", 95)),
        humidity_threshold_low=float(os.environ.get("HUMIDITY_LOW", 35)),
        humidity_threshold_high=float(os.environ.get("HUMIDITY_HIGH", 35)),
        mister_duration_seconds=int(os.environ.get("MISTER_DURATION", 600)),
        check_interval_seconds=int(os.environ.get("CHECK_INTERVAL", 60)),
        cooldown_seconds=int(os.environ.get("COOLDOWN_SECONDS", 300))
    )
    
    controller = MisterController(
        switchbot_api=switchbot_api,
        rachio_api=rachio_api,
        hub2_device_id=hub2_device_id,
        rachio_zone_id=rachio_zone_id,
        rachio_device_id=rachio_device_id,
        config=config
    )
    
    controller.run()


if __name__ == "__main__":
    main()