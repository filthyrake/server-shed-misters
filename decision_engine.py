#!/usr/bin/env python3

"""
Misting Decision Engine

This module contains the shared decision logic for determining when to start
and stop misting based on sensor readings and configuration.
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from mister_controller import SensorReading, MisterConfig


class MistingDecisionEngine:
    """
    Centralized decision logic for misting control.
    
    This class provides static methods for determining when to start and stop
    misting based on sensor readings, configuration thresholds, and system state.
    """
    
    @staticmethod
    def should_start_misting(
        reading: SensorReading,
        config: MisterConfig,
        is_misting: bool,
        is_paused: bool,
        last_mister_start: Optional[datetime]
    ) -> bool:
        """
        Determine if misting should start.
        
        Misting will start if ALL of the following are true:
        - Not currently misting
        - System is not paused
        - Cooldown period has elapsed since last start
        - Temperature is above high threshold
        - Humidity is below low threshold
        
        Args:
            reading: Current sensor reading
            config: Mister configuration with thresholds
            is_misting: Whether misting is currently active
            is_paused: Whether the system is paused
            last_mister_start: Timestamp of last mister start, or None
            
        Returns:
            True if misting should start, False otherwise
        """
        # Can't start if already misting or paused
        if is_misting or is_paused:
            return False
        
        # Check cooldown period
        if last_mister_start:
            time_since = (datetime.now(ZoneInfo("localtime")) - last_mister_start).total_seconds()
            if time_since < config.cooldown_seconds:
                return False
        
        # Both conditions must be true (AND logic)
        too_hot = reading.temperature > config.temperature_threshold_high
        too_dry = reading.humidity < config.humidity_threshold_low
        
        return too_hot and too_dry
    
    @staticmethod
    def should_stop_misting(
        reading: SensorReading,
        config: MisterConfig,
        is_misting: bool,
        last_mister_start: Optional[datetime]
    ) -> bool:
        """
        Determine if misting should stop.
        
        Misting will stop if ANY of the following are true:
        - Temperature is below low threshold (cool enough)
        - Humidity is above high threshold (humid enough)
        - Maximum duration has been reached
        
        Args:
            reading: Current sensor reading
            config: Mister configuration with thresholds
            is_misting: Whether misting is currently active
            last_mister_start: Timestamp of last mister start, or None
            
        Returns:
            True if misting should stop, False otherwise
        """
        # Can't stop if not misting
        if not is_misting:
            return False
        
        # Either condition can stop misting (OR logic)
        cool_enough = reading.temperature < config.temperature_threshold_low
        humid_enough = reading.humidity > config.humidity_threshold_high
        
        # Check max duration
        if last_mister_start:
            time_running = (datetime.now(ZoneInfo("localtime")) - last_mister_start).total_seconds()
            max_duration = time_running >= config.mister_duration_seconds
            
            return cool_enough or humid_enough or max_duration
        
        return False
