#!/usr/bin/env python3

import os
import time
import subprocess
import platform
from datetime import datetime
from dotenv import load_dotenv
from mister_controller import SwitchBotAPI, SensorReading, MisterConfig
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StandaloneMisterMonitor:
    def __init__(self):
        load_dotenv()
        
        # Initialize SwitchBot API
        switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
        switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
        
        if not all([switchbot_token, switchbot_secret]):
            raise ValueError("Missing SwitchBot credentials")
        
        self.switchbot = SwitchBotAPI(switchbot_token, switchbot_secret)
        
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
        
        self.last_alert = None
        self.alert_cooldown = 300  # 5 minutes between alerts
    
    def should_mist(self, reading: SensorReading) -> bool:
        """Check if misting conditions are met"""
        too_hot = reading.temperature > self.config.temperature_threshold_high
        too_dry = reading.humidity < self.config.humidity_threshold_low
        return too_hot and too_dry
    
    def send_alert(self, message: str):
        """Send alert notification (cross-platform)"""
        
        # Prevent spam alerts
        if self.last_alert:
            time_since = (datetime.now() - self.last_alert).total_seconds()
            if time_since < self.alert_cooldown:
                return
        
        self.last_alert = datetime.now()
        
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run([
                    "osascript", "-e", 
                    f'display notification "{message}" with title "🔥 MISTER ALERT"'
                ])
            elif platform.system() == "Linux":
                subprocess.run(["notify-send", "🔥 MISTER ALERT", message])
            elif platform.system() == "Windows":
                # Windows notification (requires plyer or similar)
                pass
            
            # Also log to console
            logger.warning(f"🚨 ALERT: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def run(self):
        if not self.hub2_device_id:
            logger.error("No Hub 2 device found")
            return
        
        logger.info("=" * 60)
        logger.info("STANDALONE MISTER MONITOR")
        logger.info("=" * 60)
        logger.info(f"Hub 2 Device: {self.hub2_device_id}")
        logger.info(f"Misting triggers when: Temp > {self.config.temperature_threshold_high}°F AND Humidity < {self.config.humidity_threshold_low}%")
        logger.info(f"Check interval: {self.config.check_interval_seconds} seconds")
        logger.info("=" * 60)
        logger.info("NOTE: This monitors only - you must manually control your Rachio valve")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        while True:
            try:
                reading = self.switchbot.get_hub2_data(self.hub2_device_id)
                
                if reading:
                    should_trigger = self.should_mist(reading)
                    
                    if should_trigger:
                        status = "🔥💦 MISTING NEEDED!"
                        alert_msg = f"Temperature: {reading.temperature:.1f}°F, Humidity: {reading.humidity}% - START MISTER NOW!"
                        self.send_alert(alert_msg)
                    else:
                        if reading.temperature > self.config.temperature_threshold_high:
                            status = "🔥 HOT (but humid enough)"
                        elif reading.humidity < self.config.humidity_threshold_low:
                            status = "🏜️ DRY (but cool enough)"  
                        else:
                            status = "✅ COMFORTABLE"
                    
                    logger.info(f"{status} | Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                    
                else:
                    logger.warning("Failed to read sensor data")
                
                time.sleep(self.config.check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("\nShutting down monitor...")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(self.config.check_interval_seconds)

def main():
    try:
        monitor = StandaloneMisterMonitor()
        monitor.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file and SwitchBot credentials")
    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    main()