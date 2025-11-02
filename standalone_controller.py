#!/usr/bin/env python3

import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from mister_controller import SwitchBotAPI, SmartHoseTimerAPI, SensorReading, MisterConfig
from decision_engine import MistingDecisionEngine
from config_validator import ConfigValidator
from state_manager import StateManager
from secrets_loader import APICredentials
from env_utils import safe_get_env_float, safe_get_env_int
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FinalMisterController:
    def __init__(self):
        load_dotenv()
        
        # Load API credentials securely from Docker secrets or environment variables
        creds = APICredentials()
        
        self.switchbot = SwitchBotAPI(creds.switchbot_token, creds.switchbot_secret)
        self.rachio = SmartHoseTimerAPI(creds.rachio_api_token)
        
        # Device IDs
        self.hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
        self.valve_id = os.environ.get("RACHIO_VALVE_ID")
        
        if not all([self.hub2_device_id, self.valve_id]):
            raise ValueError("Missing device IDs - check HUB2_DEVICE_ID and RACHIO_VALVE_ID in .env")
        
        # Configuration
        self.config = MisterConfig(
            temperature_threshold_high=safe_get_env_float("TEMP_HIGH", 95.0, min_val=ConfigValidator.MIN_TEMP, max_val=ConfigValidator.MAX_TEMP),
            temperature_threshold_low=safe_get_env_float("TEMP_LOW", 95.0, min_val=ConfigValidator.MIN_TEMP, max_val=ConfigValidator.MAX_TEMP),
            humidity_threshold_low=safe_get_env_float("HUMIDITY_LOW", 35.0, min_val=ConfigValidator.MIN_HUMIDITY, max_val=ConfigValidator.MAX_HUMIDITY),
            humidity_threshold_high=safe_get_env_float("HUMIDITY_HIGH", 35.0, min_val=ConfigValidator.MIN_HUMIDITY, max_val=ConfigValidator.MAX_HUMIDITY),
            mister_duration_seconds=safe_get_env_int("MISTER_DURATION", 600, min_val=ConfigValidator.MIN_MISTER_DURATION, max_val=ConfigValidator.MAX_MISTER_DURATION),
            check_interval_seconds=safe_get_env_int("CHECK_INTERVAL", 60, min_val=ConfigValidator.MIN_CHECK_INTERVAL, max_val=ConfigValidator.MAX_CHECK_INTERVAL),
            cooldown_seconds=safe_get_env_int("COOLDOWN_SECONDS", 300, min_val=ConfigValidator.MIN_COOLDOWN, max_val=ConfigValidator.MAX_COOLDOWN)
        )
        
        # Validate configuration
        validation_issues = ConfigValidator.validate_config(self.config)
        ConfigValidator.log_validation_results(validation_issues, self.config)
        
        if ConfigValidator.has_critical_issues(validation_issues):
            raise ValueError("Configuration validation failed with critical errors")
        
        # Initialize state manager for persistence
        self.state_manager = StateManager()
        
        # Thread safety lock for state changes
        self._state_lock = threading.Lock()
        
        # State tracking - load from persistent state
        self.last_mister_start = self.state_manager.get_last_mister_start()
        self.is_misting = False
        
        # Log restart info
        stats = self.state_manager.get_stats()
        logger.info(f"System initialized - Restarts: {stats['restart_count']}, Crashes: {stats['crash_count']}")
        if self.last_mister_start:
            logger.info(f"Restored last mister start time: {self.last_mister_start}")
    
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
        """
        Wrapper for decision engine that reads current state.
        MUST be called from within _state_lock because it accesses
        self.is_misting and self.last_mister_start.
        """
        return MistingDecisionEngine.should_start_misting(
            reading=reading,
            config=self.config,
            is_misting=self.is_misting,
            is_paused=False,  # standalone controller doesn't support pause
            last_mister_start=self.last_mister_start
        )
    
    def should_stop_misting(self, reading: SensorReading) -> bool:
        """
        Wrapper for decision engine that reads current state.
        MUST be called from within _state_lock because it accesses
        self.is_misting and self.last_mister_start.
        """
        return MistingDecisionEngine.should_stop_misting(
            reading=reading,
            config=self.config,
            is_misting=self.is_misting,
            last_mister_start=self.last_mister_start
        )
    
    def run(self):
        if not self.setup():
            logger.error("Setup failed - cannot start controller")
            return
        
        logger.info("🌡️ Starting monitoring loop... (Press Ctrl+C to stop)")
        logger.info("=" * 60)
        
        while True:
            try:
                # Get sensor reading (done outside lock - API call)
                reading = self.switchbot.get_hub2_data(self.hub2_device_id)
                
                if reading:
                    # Make decision based on current state (thread-safe)
                    with self._state_lock:
                        should_start = self.should_start_misting(reading)
                        should_stop = self.should_stop_misting(reading)
                    
                    # Execute valve actions outside lock to avoid holding lock during API calls
                    if should_start:
                        logger.warning(f"🔥💦 STARTING MISTER - Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                        
                        if self.rachio.start_watering(self.valve_id, self.config.mister_duration_seconds):
                            # Update state after successful valve action
                            with self._state_lock:
                                self.is_misting = True
                                self.last_mister_start = datetime.now(ZoneInfo("localtime"))
                                self.state_manager.record_mister_start(self.last_mister_start)
                            logger.info(f"✅ Mister started successfully for {self.config.mister_duration_seconds}s")
                        else:
                            logger.error("❌ Failed to start mister")
                    
                    elif should_stop:
                        # Calculate stop reason
                        reason = []
                        if reading.temperature < self.config.temperature_threshold_low:
                            reason.append("temp cooled")
                        if reading.humidity > self.config.humidity_threshold_high:
                            reason.append("humidity increased")
                        # Check max duration - capture time inside lock for consistency
                        with self._state_lock:
                            if self.last_mister_start:
                                runtime = (datetime.now(ZoneInfo("localtime")) - self.last_mister_start).total_seconds()
                                if runtime >= self.config.mister_duration_seconds:
                                    reason.append("max duration")
                        
                        logger.info(f"💧 STOPPING MISTER ({', '.join(reason)}) - Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                        
                        if self.rachio.stop_watering(self.valve_id):
                            # Update state after successful valve action
                            with self._state_lock:
                                self.is_misting = False
                            logger.info("✅ Mister stopped successfully")
                        else:
                            logger.error("❌ Failed to stop mister")
                    
                    else:
                        # Status reporting (thread-safe reads)
                        status_parts = []
                        
                        with self._state_lock:
                            is_misting = self.is_misting
                            last_mister_start = self.last_mister_start
                        
                        if is_misting:
                            if last_mister_start:
                                runtime = (datetime.now(ZoneInfo("localtime")) - last_mister_start).total_seconds()
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
                            if last_mister_start:
                                cooldown_elapsed = (datetime.now(ZoneInfo("localtime")) - last_mister_start).total_seconds()
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
                # Thread-safe read of misting state for shutdown
                # Note: It's safe to release lock before stopping valve since we're shutting down
                # and no other thread will modify state after this point
                with self._state_lock:
                    is_misting = self.is_misting
                if is_misting:
                    logger.info("Stopping mister before exit...")
                    self.rachio.stop_watering(self.valve_id)
                self.state_manager.graceful_shutdown()
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