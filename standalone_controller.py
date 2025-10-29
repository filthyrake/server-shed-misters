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

class SmartHoseTimerAPI:
    """API client for Rachio Smart Hose Timer"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://cloud-rest.rach.io"
        
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
            
            if response.status_code == 200:
                return response.json() if response.content else {"success": True}
            elif response.status_code == 204:
                return {"success": True}
            else:
                logger.error(f"Smart Hose Timer API error {response.status_code}: {response.text}")
                return None
        except Exception as e:
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
    
    def get_valve_status(self, valve_id: str) -> dict:
        """Get valve status"""
        # This would require finding the right endpoint for valve status
        # For now, we'll rely on our own state tracking
        return {}

class FinalMisterController:
    def __init__(self):
        load_dotenv()
        
        # Initialize APIs
        switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
        switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
        rachio_token = os.environ.get("RACHIO_API_TOKEN")
        
        if not all([switchbot_token, switchbot_secret, rachio_token]):
            raise ValueError("Missing required API credentials")
        
        self.switchbot = SwitchBotAPI(switchbot_token, switchbot_secret)
        self.rachio = SmartHoseTimerAPI(rachio_token)
        
        # Device IDs
        self.hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
        self.valve_id = os.environ.get("RACHIO_VALVE_ID")
        
        if not all([self.hub2_device_id, self.valve_id]):
            raise ValueError("Missing device IDs - check HUB2_DEVICE_ID and RACHIO_VALVE_ID in .env")
        
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
        
        # State tracking
        self.last_mister_start = None
        self.is_misting = False
    
    def setup(self):
        """Test connections and display configuration"""
        logger.info("=" * 60)
        logger.info("FINAL MISTER CONTROLLER")
        logger.info("=" * 60)
        
        # Test SwitchBot connection
        reading = self.switchbot.get_hub2_data(self.hub2_device_id)
        if not reading:
            logger.error("Cannot connect to SwitchBot Hub 2")
            return False
        
        logger.info(f"✓ SwitchBot Hub 2 connected")
        logger.info(f"  Current: {reading.temperature:.1f}°F, {reading.humidity}% humidity")
        
        logger.info(f"✓ Smart Hose Timer valve ready")
        logger.info(f"  Valve ID: {self.valve_id}")
        
        logger.info("=" * 60)
        logger.info("MISTING LOGIC:")
        logger.info(f"  Start when: Temp > {self.config.temperature_threshold_high}°F AND Humidity < {self.config.humidity_threshold_low}%")
        logger.info(f"  Stop when:  Temp < {self.config.temperature_threshold_low}°F OR  Humidity > {self.config.humidity_threshold_high}%")
        logger.info(f"  Duration: {self.config.mister_duration_seconds // 60} minutes ({self.config.mister_duration_seconds}s)")
        logger.info(f"  Cooldown: {self.config.cooldown_seconds // 60} minutes ({self.config.cooldown_seconds}s)")
        logger.info(f"  Check every: {self.config.check_interval_seconds}s")
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
        
        logger.info("🌡️ Starting monitoring loop... (Press Ctrl+C to stop)")
        logger.info("=" * 60)
        
        while True:
            try:
                reading = self.switchbot.get_hub2_data(self.hub2_device_id)
                
                if reading:
                    if self.should_start_misting(reading):
                        logger.warning(f"🔥💦 STARTING MISTER - Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                        
                        if self.rachio.start_watering(self.valve_id, self.config.mister_duration_seconds):
                            self.is_misting = True
                            self.last_mister_start = datetime.now()
                            logger.info(f"✅ Mister started successfully for {self.config.mister_duration_seconds}s")
                        else:
                            logger.error("❌ Failed to start mister")
                    
                    elif self.should_stop_misting(reading):
                        reason = []
                        if reading.temperature < self.config.temperature_threshold_low:
                            reason.append("temp cooled")
                        if reading.humidity > self.config.humidity_threshold_high:
                            reason.append("humidity increased")
                        if self.last_mister_start:
                            runtime = (datetime.now() - self.last_mister_start).total_seconds()
                            if runtime >= self.config.mister_duration_seconds:
                                reason.append("max duration")
                        
                        logger.info(f"💧 STOPPING MISTER ({', '.join(reason)}) - Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                        
                        if self.rachio.stop_watering(self.valve_id):
                            self.is_misting = False
                            logger.info("✅ Mister stopped successfully")
                        else:
                            logger.error("❌ Failed to stop mister")
                    
                    else:
                        # Status reporting
                        status_parts = []
                        
                        if self.is_misting:
                            if self.last_mister_start:
                                runtime = (datetime.now() - self.last_mister_start).total_seconds()
                                remaining = self.config.mister_duration_seconds - runtime
                                status_parts.append(f"💦 MISTING ({remaining:.0f}s left)")
                            else:
                                status_parts.append("💦 MISTING")
                        else:
                            if reading.temperature > self.config.temperature_threshold_high:
                                status_parts.append("🔥 HOT")
                            if reading.humidity < self.config.humidity_threshold_low:
                                status_parts.append("🏜️ DRY")
                            
                            if not status_parts:
                                status_parts.append("✅ COMFORTABLE")
                            
                            # Cooldown info
                            if self.last_mister_start:
                                cooldown_elapsed = (datetime.now() - self.last_mister_start).total_seconds()
                                if cooldown_elapsed < self.config.cooldown_seconds:
                                    cooldown_remaining = self.config.cooldown_seconds - cooldown_elapsed
                                    status_parts.append(f"⏰ COOLDOWN ({cooldown_remaining:.0f}s)")
                        
                        status = " | ".join(status_parts)
                        logger.info(f"{status} | Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                else:
                    logger.warning("⚠️ Failed to read sensor data")
                
                time.sleep(self.config.check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Shutting down...")
                if self.is_misting:
                    logger.info("Stopping mister before exit...")
                    self.rachio.stop_watering(self.valve_id)
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                time.sleep(self.config.check_interval_seconds)

def main():
    try:
        controller = FinalMisterController()
        controller.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file")
    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    main()