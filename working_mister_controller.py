#!/usr/bin/env python3

import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from mister_controller import SwitchBotAPI, SensorReading, MisterConfig
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkingRachioAPI:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.rach.io/1/public"
        self.person_id = None
        self.working_zone_id = None
        self.working_device_id = None
    
    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None):
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
            
            if response.status_code in [200, 204]:
                return response.json() if response.content else {"success": True}
            else:
                logger.error(f"Rachio API error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Rachio API exception: {e}")
            return None
    
    def find_working_zone(self):
        """Find the first available zone that we can control"""
        
        # Get person info
        person_info = self._make_request("/person/info")
        if not person_info:
            return False
            
        self.person_id = person_info["id"]
        logger.info(f"Connected to Rachio account: {self.person_id}")
        
        # Get full person data
        person_data = self._make_request(f"/person/{self.person_id}")
        if not person_data:
            return False
        
        devices = person_data.get('devices', [])
        
        if not devices:
            logger.warning("No traditional Rachio controllers found")
            
            # Try Smart Hose Timer API endpoints
            logger.info("Checking for Smart Hose Timer...")
            
            # Try various endpoints for Smart Hose Timer
            sht_endpoints = [
                f"/valve/listBaseStations/{self.person_id}",
                "/smartHoseTimer/list",
                "/valve/list"
            ]
            
            for endpoint in sht_endpoints:
                result = self._make_request(endpoint)
                if result:
                    logger.info(f"Found Smart Hose Timer data at {endpoint}")
                    # Handle Smart Hose Timer result
                    return self._handle_smart_hose_timer(result)
            
            return False
        
        # Handle traditional controllers
        for device in devices:
            device_name = device.get('name', 'Unknown')
            logger.info(f"Found device: {device_name} ({device['id']})")
            
            zones = device.get('zones', [])
            enabled_zones = [z for z in zones if z.get('enabled', False)]
            
            if enabled_zones:
                # Use the first enabled zone
                zone = enabled_zones[0]
                zone_name = zone.get('name', 'Unknown')
                
                logger.info(f"Testing zone: {zone_name} ({zone['id']})")
                
                # Test if we can control this zone
                test_result = self._make_request("/zone/start", "PUT", {
                    "id": zone['id'],
                    "duration": 1  # 1 second test
                })
                
                if test_result:
                    self.working_zone_id = zone['id']
                    self.working_device_id = device['id']
                    logger.info(f"✓ Working zone found: {zone_name}")
                    
                    # Stop it immediately
                    self.stop_watering()
                    
                    return True
                else:
                    logger.warning(f"Cannot control zone: {zone_name}")
        
        return False
    
    def _handle_smart_hose_timer(self, data):
        """Handle Smart Hose Timer API response"""
        # This would need to be implemented based on actual API response
        logger.info("Smart Hose Timer handling not yet implemented")
        return False
    
    def start_watering(self, duration: int) -> bool:
        """Start watering for the specified duration in seconds"""
        if not self.working_zone_id:
            logger.error("No working zone found")
            return False
        
        logger.info(f"Starting watering for {duration} seconds")
        result = self._make_request("/zone/start", "PUT", {
            "id": self.working_zone_id,
            "duration": duration
        })
        
        return result is not None
    
    def stop_watering(self) -> bool:
        """Stop all watering"""
        if not self.working_device_id:
            logger.error("No working device found")
            return False
        
        logger.info("Stopping all watering")
        result = self._make_request("/device/stop_water", "PUT", {
            "id": self.working_device_id
        })
        
        return result is not None

class WorkingMisterController:
    def __init__(self):
        load_dotenv()
        
        # Initialize APIs
        switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
        switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
        rachio_token = os.environ.get("RACHIO_API_TOKEN")
        
        if not all([switchbot_token, switchbot_secret, rachio_token]):
            raise ValueError("Missing required API credentials")
        
        self.switchbot = SwitchBotAPI(switchbot_token, switchbot_secret)
        self.rachio = WorkingRachioAPI(rachio_token)
        
        # Get Hub 2 device
        hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
        if not hub2_device_id:
            devices = self.switchbot.get_devices()
            hub2_devices = [d for d in devices if d.get("deviceType") == "Hub 2"]
            if hub2_devices:
                hub2_device_id = hub2_devices[0]['deviceId']
        
        self.hub2_device_id = hub2_device_id
        
        # Configuration
        self.config = MisterConfig(
            temperature_threshold_high=float(os.environ.get("TEMP_HIGH", 95)),
            temperature_threshold_low=float(os.environ.get("TEMP_LOW", 95)),
            humidity_threshold_low=float(os.environ.get("HUMIDITY_LOW", 35)),
            humidity_threshold_high=float(os.environ.get("HUMIDITY_HIGH", 35)),
            mister_duration_seconds=int(os.environ.get("MISTER_DURATION", 600)),
            check_interval_seconds=int(os.environ.get("CHECK_INTERVAL", 60)),
            cooldown_seconds=int(os.environ.get("COOLDOWN_SECONDS", 300))
        )
        
        self.last_mister_start = None
        self.is_misting = False
    
    def setup(self):
        """Initialize and test connections"""
        logger.info("=" * 60)
        logger.info("WORKING MISTER CONTROLLER SETUP")
        logger.info("=" * 60)
        
        # Test SwitchBot
        if not self.hub2_device_id:
            logger.error("No Hub 2 device found")
            return False
        
        reading = self.switchbot.get_hub2_data(self.hub2_device_id)
        if not reading:
            logger.error("Cannot read from Hub 2")
            return False
        
        logger.info(f"✓ SwitchBot Hub 2 connected - Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
        
        # Test Rachio
        if not self.rachio.find_working_zone():
            logger.error("No working Rachio zone found")
            return False
        
        logger.info(f"✓ Rachio zone connected - Zone: {self.rachio.working_zone_id}")
        
        logger.info("=" * 60)
        logger.info("CONFIGURATION:")
        logger.info(f"  Start misting when: Temp > {self.config.temperature_threshold_high}°F AND Humidity < {self.config.humidity_threshold_low}%")
        logger.info(f"  Stop misting when: Temp < {self.config.temperature_threshold_low}°F OR Humidity > {self.config.humidity_threshold_high}%")
        logger.info(f"  Misting duration: {self.config.mister_duration_seconds} seconds")
        logger.info(f"  Cooldown: {self.config.cooldown_seconds} seconds")
        logger.info("=" * 60)
        
        return True
    
    def should_start_misting(self, reading: SensorReading) -> bool:
        if self.is_misting:
            return False
        
        # Check cooldown
        if self.last_mister_start:
            time_since = (datetime.now() - self.last_mister_start).total_seconds()
            if time_since < self.config.cooldown_seconds:
                return False
        
        # Both conditions must be true
        too_hot = reading.temperature > self.config.temperature_threshold_high
        too_dry = reading.humidity < self.config.humidity_threshold_low
        
        return too_hot and too_dry
    
    def should_stop_misting(self, reading: SensorReading) -> bool:
        if not self.is_misting:
            return False
        
        # Either condition can stop misting
        cool_enough = reading.temperature < self.config.temperature_threshold_low
        humid_enough = reading.humidity > self.config.humidity_threshold_high
        
        # Or max duration reached
        if self.last_mister_start:
            time_running = (datetime.now() - self.last_mister_start).total_seconds()
            max_duration = time_running >= self.config.mister_duration_seconds
            
            return cool_enough or humid_enough or max_duration
        
        return False
    
    def run(self):
        if not self.setup():
            logger.error("Setup failed - cannot start controller")
            return
        
        logger.info("Starting monitoring loop...")
        
        while True:
            try:
                reading = self.switchbot.get_hub2_data(self.hub2_device_id)
                
                if reading:
                    if self.should_start_misting(reading):
                        logger.warning(f"🔥 STARTING MISTER - Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
                        
                        if self.rachio.start_watering(self.config.mister_duration_seconds):
                            self.is_misting = True
                            self.last_mister_start = datetime.now()
                            logger.info("✓ Mister started successfully")
                        else:
                            logger.error("Failed to start mister")
                    
                    elif self.should_stop_misting(reading):
                        logger.info(f"💧 STOPPING MISTER - Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
                        
                        if self.rachio.stop_watering():
                            self.is_misting = False
                            logger.info("✓ Mister stopped successfully")
                        else:
                            logger.error("Failed to stop mister")
                    
                    else:
                        status = "🌡️ MONITORING"
                        if self.is_misting:
                            runtime = (datetime.now() - self.last_mister_start).total_seconds()
                            status = f"💦 MISTING ({runtime:.0f}s)"
                        elif self.last_mister_start:
                            cooldown = (datetime.now() - self.last_mister_start).total_seconds()
                            if cooldown < self.config.cooldown_seconds:
                                remaining = self.config.cooldown_seconds - cooldown
                                status = f"⏰ COOLDOWN ({remaining:.0f}s)"
                        
                        logger.info(f"{status} | Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
                else:
                    logger.warning("Failed to read sensor data")
                
                time.sleep(self.config.check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("\nShutting down...")
                if self.is_misting:
                    logger.info("Stopping mister before exit...")
                    self.rachio.stop_watering()
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(self.config.check_interval_seconds)

def main():
    try:
        controller = WorkingMisterController()
        controller.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file and API credentials")
    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    main()