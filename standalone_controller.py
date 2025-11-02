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
import requests

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
        
        # Validate device IDs exist
        if not self.hub2_device_id:
            raise ValueError(
                "HUB2_DEVICE_ID is required. Run tools/find_devices.py to discover your device ID"
            )
        
        if not self.valve_id:
            raise ValueError(
                "RACHIO_VALVE_ID is required. Run tools/find_devices.py to discover your valve ID"
            )
        
        # Validate device ID format (basic sanity check for alphanumeric with hyphens)
        if len(self.hub2_device_id) < ConfigValidator.MIN_DEVICE_ID_LENGTH or not self.hub2_device_id.replace('-', '').isalnum():
            logger.warning(f"HUB2_DEVICE_ID format looks suspicious: {self.hub2_device_id}")
        
        if len(self.valve_id) < ConfigValidator.MIN_DEVICE_ID_LENGTH or not self.valve_id.replace('-', '').isalnum():
            logger.warning(f"RACHIO_VALVE_ID format looks suspicious: {self.valve_id}")
        
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
        
        # Test connection to SwitchBot Hub 2 on startup
        logger.info("Testing SwitchBot Hub 2 connection...")
        test_reading = self.switchbot.get_hub2_data(self.hub2_device_id)
        if not test_reading:
            raise ValueError(f"Cannot connect to SwitchBot Hub 2 with ID: {self.hub2_device_id}")
        logger.info(f"✓ SwitchBot Hub 2 connected: {test_reading.temperature:.1f}°F, {test_reading.humidity}%")
        
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
    
    def _emergency_stop_with_retries(self) -> bool:
        """
        Attempt to stop the valve with retry logic for hardware safety.
        Returns True if successful, False if all retries failed.
        Note: Only updates is_misting state; last_mister_start is intentionally not updated here,
        as cooldown is calculated from the original start time. This is correct and safe behavior.
        """
        MAX_RETRY_ATTEMPTS = 3
        valve_stopped = False
        
        try:
            if self.rachio.stop_watering(self.valve_id):
                with self._state_lock:
                    self.is_misting = False
                logger.info("Emergency valve stop successful")
                valve_stopped = True
            else:
                raise Exception("stop_watering returned False")
        except Exception as stop_error:
            logger.critical(f"FAILED TO STOP VALVE IN EMERGENCY: {stop_error}")
            # Retry with exponential backoff: 1s, 2s, 4s
            for retry in range(MAX_RETRY_ATTEMPTS):
                logger.warning(f"Emergency stop retry attempt {retry + 1}/{MAX_RETRY_ATTEMPTS}")
                time.sleep(2 ** retry)  # 2^0=1s, 2^1=2s, 2^2=4s
                try:
                    if self.rachio.stop_watering(self.valve_id):
                        with self._state_lock:
                            self.is_misting = False
                        logger.info(f"Emergency valve stop successful on retry {retry + 1}")
                        valve_stopped = True
                        break
                except Exception as retry_error:
                    logger.critical(f"Retry {retry + 1} failed: {retry_error}")
            
            if not valve_stopped:
                logger.critical("ALL EMERGENCY STOP RETRIES FAILED - MANUAL INTERVENTION REQUIRED")
        
        return valve_stopped
    
    def _enter_safe_mode(self, safe_mode_wait_seconds: int):
        """
        Enter safe mode: stop valve if misting and wait before retrying.
        """
        logger.critical("Too many consecutive errors, entering safe mode")
        
        # Thread-safe check and emergency stop if misting
        with self._state_lock:
            is_misting = self.is_misting
        
        if is_misting:
            logger.warning("Emergency stop: shutting off valve")
            self._emergency_stop_with_retries()
        
        # Longer backoff in safe mode (5 minutes)
        logger.info(f"Safe mode: waiting {safe_mode_wait_seconds} seconds before retry")
        time.sleep(safe_mode_wait_seconds)
    
    def run(self):
        if not self.setup():
            logger.error("Setup failed - cannot start controller")
            return
        
        logger.info("🌡️ Starting monitoring loop... (Press Ctrl+C to stop)")
        logger.info("=" * 60)
        
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 5
        SAFE_MODE_WAIT_SECONDS = 300
        
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
                consecutive_errors = 0  # Reset on success
                
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
                consecutive_errors += 1
                logger.critical(f"Unexpected error in controller loop ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {e}", exc_info=True)
                
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    self._enter_safe_mode(SAFE_MODE_WAIT_SECONDS)
                    consecutive_errors = 0  # Reset after safe mode wait
                else:
                    # Normal backoff
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