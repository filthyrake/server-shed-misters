#!/usr/bin/env python3

import os
import time
from datetime import datetime
from dotenv import load_dotenv
from mister_controller import SwitchBotAPI, SensorReading, MisterConfig
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
    switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
    hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
    
    if not all([switchbot_token, switchbot_secret]):
        logger.error("Missing SWITCHBOT_TOKEN or SWITCHBOT_SECRET")
        return
    
    api = SwitchBotAPI(switchbot_token, switchbot_secret)
    
    # Auto-detect Hub 2 if not specified
    if not hub2_device_id:
        devices = api.get_devices()
        if devices:
            hub2_devices = [d for d in devices if d.get("deviceType") == "Hub 2"]
            if hub2_devices:
                # You have two Hub 2 devices, let's list them
                print("\nAvailable Hub 2 devices:")
                for i, device in enumerate(hub2_devices):
                    status = api.get_device_status(device['deviceId'])
                    temp = status.get('temperature', 'N/A') if status else 'N/A'
                    humidity = status.get('humidity', 'N/A') if status else 'N/A'
                    print(f"{i+1}. {device.get('deviceName')} - Temp: {temp}°F, Humidity: {humidity}%")
                
                if len(hub2_devices) == 1:
                    hub2_device_id = hub2_devices[0]['deviceId']
                else:
                    choice = input("Select Hub 2 device number (or press Enter for #1): ").strip()
                    idx = int(choice) - 1 if choice else 0
                    hub2_device_id = hub2_devices[idx]['deviceId']
                
                print(f"Using Hub 2: {hub2_devices[idx].get('deviceName')}")
    
    config = MisterConfig(
        temperature_threshold_high=float(os.environ.get("TEMP_HIGH", 95)),
        temperature_threshold_low=float(os.environ.get("TEMP_LOW", 95)),
        humidity_threshold_low=float(os.environ.get("HUMIDITY_LOW", 35)),
        humidity_threshold_high=float(os.environ.get("HUMIDITY_HIGH", 35)),
        mister_duration_seconds=int(os.environ.get("MISTER_DURATION", 600)),
        check_interval_seconds=int(os.environ.get("CHECK_INTERVAL", 10)),
        cooldown_seconds=int(os.environ.get("COOLDOWN_SECONDS", 300))
    )
    
    logger.info("=" * 60)
    logger.info("MISTER CONTROLLER - MONITORING MODE")
    logger.info("=" * 60)
    logger.info(f"Hub 2 Device ID: {hub2_device_id}")
    logger.info(f"Temperature threshold: > {config.temperature_threshold_high}°F")
    logger.info(f"Humidity threshold: < {config.humidity_threshold_low}%")
    logger.info(f"Check interval: {config.check_interval_seconds} seconds")
    logger.info("=" * 60)
    logger.info("NOTE: Rachio control not connected - monitoring only")
    logger.info("=" * 60)
    
    last_mister_trigger = None
    
    while True:
        try:
            reading = api.get_hub2_data(hub2_device_id)
            
            if reading:
                # Check if we should trigger misting
                should_mist = (reading.temperature > config.temperature_threshold_high and 
                              reading.humidity < config.humidity_threshold_low)
                
                # Check cooldown
                can_mist = True
                if last_mister_trigger:
                    time_since = (datetime.now() - last_mister_trigger).total_seconds()
                    if time_since < config.cooldown_seconds:
                        can_mist = False
                        cooldown_remaining = config.cooldown_seconds - time_since
                
                status = "🌡️"
                if should_mist and can_mist:
                    status = "💦 MISTING NEEDED!"
                    logger.warning(f"MISTING TRIGGERED - Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
                    last_mister_trigger = datetime.now()
                elif should_mist and not can_mist:
                    status = f"⏰ COOLDOWN ({cooldown_remaining:.0f}s)"
                elif reading.temperature > config.temperature_threshold_high:
                    status = "🔥 HOT (but humid enough)"
                elif reading.humidity < config.humidity_threshold_low:
                    status = "🏜️ DRY (but cool enough)"
                else:
                    status = "✅ COMFORTABLE"
                
                logger.info(f"{status} | Temp: {reading.temperature}°F, Humidity: {reading.humidity}%")
            else:
                logger.warning("Failed to get sensor reading")
            
            time.sleep(config.check_interval_seconds)
            
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(config.check_interval_seconds)

if __name__ == "__main__":
    main()