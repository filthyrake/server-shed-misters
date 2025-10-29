#!/usr/bin/env python3

"""
Misting Decision Engine - Shared logic for determining when to start/stop misting.

This module provides a centralized decision engine that both api_server.py and 
standalone_controller.py use to maintain consistent misting logic.
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from mister_controller import SensorReading, MisterConfig


class MistingDecisionEngine:
    """
    Centralized decision logic for misting control.
    
    This class implements the core business logic for determining when to start
    and stop misting based on sensor readings, configuration thresholds, and 
    timing constraints.
    """
    
    @staticmethod
    def _get_compatible_now(reference_datetime: Optional[datetime]) -> datetime:
        """
        Get current datetime compatible with the reference datetime's timezone awareness.
        
        If reference_datetime is timezone-aware, returns timezone-aware now().
        If reference_datetime is naive, returns naive now().
        If reference_datetime is None, returns timezone-aware now() by default.
        
        Args:
            reference_datetime: Optional reference datetime to match timezone awareness
            
        Returns:
            Current datetime with matching timezone awareness
        """
        if reference_datetime is not None and reference_datetime.tzinfo is not None:
            return datetime.now(ZoneInfo("localtime"))
        else:
            return datetime.now()
    
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
        
        Misting starts when ALL conditions are met:
        - Not currently misting
        - System is not paused
        - Cooldown period has elapsed (if applicable)
        - Temperature is above high threshold AND
        - Humidity is below low threshold
        
        Args:
            reading: Current sensor reading
            config: Mister configuration with thresholds
            is_misting: Whether misting is currently active
            is_paused: Whether the system is paused
            last_mister_start: Timestamp of last misting start (None if never started)
            
        Returns:
            True if misting should start, False otherwise
        """
        # Cannot start if already misting or paused
        if is_misting or is_paused:
            return False
        
        # Check cooldown period
        if last_mister_start:
            now = MistingDecisionEngine._get_compatible_now(last_mister_start)
            time_since = (now - last_mister_start).total_seconds()
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
        
        Misting stops when ANY condition is met:
        - Temperature is below low threshold OR
        - Humidity is above high threshold OR
        - Maximum duration has been reached
        
        Args:
            reading: Current sensor reading
            config: Mister configuration with thresholds
            is_misting: Whether misting is currently active
            last_mister_start: Timestamp of last misting start (None if never started)
            
        Returns:
            True if misting should stop, False otherwise
        """
        # Cannot stop if not misting
        if not is_misting:
            return False
        
        # Either condition can stop misting (OR logic)
        cool_enough = reading.temperature < config.temperature_threshold_low
        humid_enough = reading.humidity > config.humidity_threshold_high
        
        # Check max duration
        if last_mister_start:
            now = MistingDecisionEngine._get_compatible_now(last_mister_start)
            time_running = (now - last_mister_start).total_seconds()
            max_duration = time_running >= config.mister_duration_seconds
            
            return cool_enough or humid_enough or max_duration
        
        return False
