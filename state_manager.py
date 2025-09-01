#!/usr/bin/env python3

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class StateManager:
    """Manages persistent state across application restarts"""
    
    def __init__(self, state_file: str = "./data/state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Default state
        self.default_state = {
            "is_paused": False,
            "last_mister_start": None,
            "total_runtime_seconds": 0,
            "last_shutdown_time": None,
            "restart_count": 0,
            "crash_count": 0
        }
        
        self.state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Load state from persistent storage"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                # Increment restart count
                state["restart_count"] = state.get("restart_count", 0) + 1
                
                # Check if this was an unexpected restart (crash)
                last_shutdown = state.get("last_shutdown_time")
                if last_shutdown is None:
                    state["crash_count"] = state.get("crash_count", 0) + 1
                    logger.warning(f"Detected unexpected restart. Crash count: {state['crash_count']}")
                
                # Clear shutdown time
                state["last_shutdown_time"] = None
                
                logger.info(f"Loaded state from {self.state_file}")
                logger.info(f"Restart count: {state['restart_count']}, Crash count: {state['crash_count']}")
                
                # Validate and merge with defaults
                merged_state = self.default_state.copy()
                merged_state.update(state)
                
                return merged_state
            else:
                logger.info("No existing state file, using defaults")
                return self.default_state.copy()
                
        except Exception as e:
            logger.error(f"Failed to load state: {e}, using defaults")
            return self.default_state.copy()
    
    def save_state(self):
        """Save current state to persistent storage"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            logger.debug(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def update_state(self, **kwargs):
        """Update state and save immediately"""
        for key, value in kwargs.items():
            if isinstance(value, datetime):
                value = value.isoformat()
            self.state[key] = value
        self.save_state()
    
    def get_state(self, key: str, default=None):
        """Get a state value"""
        return self.state.get(key, default)
    
    def is_paused(self) -> bool:
        """Check if the system was paused before restart"""
        return self.state.get("is_paused", False)
    
    def set_paused(self, paused: bool):
        """Update paused state"""
        self.update_state(is_paused=paused)
    
    def record_mister_start(self, start_time: datetime):
        """Record when misting started"""
        self.update_state(last_mister_start=start_time.isoformat())
    
    def get_last_mister_start(self) -> datetime:
        """Get the last mister start time"""
        last_start = self.state.get("last_mister_start")
        if last_start:
            try:
                dt = datetime.fromisoformat(last_start)
                # If the datetime is naive (no timezone), assume it's local time
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("localtime"))
                return dt
            except:
                pass
        return None
    
    def record_runtime(self, additional_seconds: int):
        """Add to total runtime"""
        current_total = self.state.get("total_runtime_seconds", 0)
        self.update_state(total_runtime_seconds=current_total + additional_seconds)
    
    def graceful_shutdown(self):
        """Record graceful shutdown"""
        self.update_state(last_shutdown_time=datetime.now(ZoneInfo("localtime")).isoformat())
        logger.info("Graceful shutdown recorded")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reliability statistics"""
        return {
            "total_runtime_seconds": self.state.get("total_runtime_seconds", 0),
            "restart_count": self.state.get("restart_count", 0),
            "crash_count": self.state.get("crash_count", 0),
            "uptime_percentage": self._calculate_uptime_percentage()
        }
    
    def _calculate_uptime_percentage(self) -> float:
        """Calculate uptime percentage (simplified)"""
        restarts = self.state.get("restart_count", 1)
        crashes = self.state.get("crash_count", 0)
        if restarts == 0:
            return 100.0
        return max(0.0, (1.0 - (crashes / restarts)) * 100.0)