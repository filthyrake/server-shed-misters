#!/usr/bin/env python3

import os
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import logging

# Import our mister controller components
from mister_controller import SwitchBotAPI, SensorReading, MisterConfig
from final_mister_controller import SmartHoseTimerAPI
from state_manager import StateManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Mister Controller API", version="1.0.0")

# Pydantic models
class StatusResponse(BaseModel):
    is_running: bool
    is_paused: bool
    is_misting: bool
    current_temp: Optional[float] = None
    current_humidity: Optional[float] = None
    last_reading_time: Optional[str] = None
    last_mister_start: Optional[str] = None
    next_check_time: Optional[str] = None
    uptime_seconds: int
    config: Dict[str, Any]

class ControlResponse(BaseModel):
    success: bool
    message: str
    new_status: str

# Global controller state
class MisterControllerState:
    def __init__(self):
        self.is_running = False
        self.is_misting = False
        self.last_reading = None
        self.last_reading_time = None
        self.start_time = datetime.now()
        self.controller_thread = None
        self.stop_event = threading.Event()
        
        # Initialize state manager
        self.state_manager = StateManager()
        self.is_paused = self.state_manager.is_paused()
        self.last_mister_start = self.state_manager.get_last_mister_start()
        
        # Initialize APIs
        load_dotenv()
        self.switchbot = None
        self.rachio = None
        self.config = None
        self.hub2_device_id = None
        self.valve_id = None
        
        self._setup_apis()
        
        # Log restart info
        stats = self.state_manager.get_stats()
        logger.info(f"System initialized - Restarts: {stats['restart_count']}, Crashes: {stats['crash_count']}")
        if self.is_paused:
            logger.info("System was paused before restart - remaining paused")
    
    def _setup_apis(self):
        try:
            switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
            switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
            rachio_token = os.environ.get("RACHIO_API_TOKEN")
            
            if not all([switchbot_token, switchbot_secret, rachio_token]):
                raise ValueError("Missing API credentials")
            
            self.switchbot = SwitchBotAPI(switchbot_token, switchbot_secret)
            self.rachio = SmartHoseTimerAPI(rachio_token)
            
            self.hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
            self.valve_id = os.environ.get("RACHIO_VALVE_ID")
            
            self.config = MisterConfig(
                temperature_threshold_high=float(os.environ.get("TEMP_HIGH", 95)),
                temperature_threshold_low=float(os.environ.get("TEMP_LOW", 95)),
                humidity_threshold_low=float(os.environ.get("HUMIDITY_LOW", 35)),
                humidity_threshold_high=float(os.environ.get("HUMIDITY_HIGH", 35)),
                mister_duration_seconds=int(os.environ.get("MISTER_DURATION", 600)),
                check_interval_seconds=int(os.environ.get("CHECK_INTERVAL", 60)),
                cooldown_seconds=int(os.environ.get("COOLDOWN_SECONDS", 300))
            )
            
            logger.info("APIs initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup APIs: {e}")
            raise
    
    def should_start_misting(self, reading: SensorReading) -> bool:
        if self.is_misting or self.is_paused:
            return False
        
        if self.last_mister_start:
            time_since = (datetime.now() - self.last_mister_start).total_seconds()
            if time_since < self.config.cooldown_seconds:
                return False
        
        too_hot = reading.temperature > self.config.temperature_threshold_high
        too_dry = reading.humidity < self.config.humidity_threshold_low
        
        return too_hot and too_dry
    
    def should_stop_misting(self, reading: SensorReading) -> bool:
        if not self.is_misting:
            return False
        
        cool_enough = reading.temperature < self.config.temperature_threshold_low
        humid_enough = reading.humidity > self.config.humidity_threshold_high
        
        if self.last_mister_start:
            time_running = (datetime.now() - self.last_mister_start).total_seconds()
            max_duration = time_running >= self.config.mister_duration_seconds
            
            return cool_enough or humid_enough or max_duration
        
        return False
    
    def controller_loop(self):
        """Main controller loop running in background thread"""
        logger.info("Controller loop started")
        
        while not self.stop_event.is_set():
            try:
                if not self.is_paused:
                    # Get sensor reading
                    reading = self.switchbot.get_hub2_data(self.hub2_device_id)
                    
                    if reading:
                        self.last_reading = reading
                        self.last_reading_time = datetime.now()
                        
                        if self.should_start_misting(reading):
                            logger.warning(f"Starting mister - Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                            
                            if self.rachio.start_watering(self.valve_id, self.config.mister_duration_seconds):
                                self.is_misting = True
                                self.last_mister_start = datetime.now()
                                self.state_manager.record_mister_start(self.last_mister_start)
                                logger.info("Mister started successfully")
                            else:
                                logger.error("Failed to start mister")
                        
                        elif self.should_stop_misting(reading):
                            logger.info(f"Stopping mister - Temp: {reading.temperature:.1f}°F, Humidity: {reading.humidity}%")
                            
                            if self.rachio.stop_watering(self.valve_id):
                                self.is_misting = False
                                logger.info("Mister stopped successfully")
                            else:
                                logger.error("Failed to stop mister")
                    
                # Wait for next check
                self.stop_event.wait(self.config.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Controller loop error: {e}")
                self.stop_event.wait(self.config.check_interval_seconds)
        
        logger.info("Controller loop stopped")
    
    def start(self):
        if self.is_running:
            return False, "Controller is already running"
        
        self.stop_event.clear()
        self.controller_thread = threading.Thread(target=self.controller_loop, daemon=True)
        self.controller_thread.start()
        self.is_running = True
        
        logger.info("Controller started")
        return True, "Controller started successfully"
    
    def stop(self):
        if not self.is_running:
            return False, "Controller is not running"
        
        self.stop_event.set()
        if self.controller_thread:
            self.controller_thread.join(timeout=5)
        
        # Emergency stop misting
        if self.is_misting:
            try:
                self.rachio.stop_watering(self.valve_id)
                self.is_misting = False
            except:
                pass
        
        self.is_running = False
        logger.info("Controller stopped")
        return True, "Controller stopped successfully"
    
    def pause(self):
        if not self.is_running:
            return False, "Controller is not running"
        if self.is_paused:
            return False, "Controller is already paused"
        
        self.is_paused = True
        self.state_manager.set_paused(True)
        logger.info("Controller paused")
        return True, "Controller paused"
    
    def resume(self):
        if not self.is_running:
            return False, "Controller is not running"
        if not self.is_paused:
            return False, "Controller is not paused"
        
        self.is_paused = False
        self.state_manager.set_paused(False)
        logger.info("Controller resumed")
        return True, "Controller resumed"

# Global state instance
state = MisterControllerState()

@app.on_event("startup")
async def startup_event():
    """Start the controller automatically when the API starts"""
    success, message = state.start()
    if success:
        logger.info("Mister controller started automatically")
    else:
        logger.warning(f"Failed to start controller: {message}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the controller when the API shuts down"""
    state.state_manager.graceful_shutdown()
    success, message = state.stop()
    logger.info("Mister controller stopped gracefully")

@app.get("/", response_class=HTMLResponse)
async def get_web_ui():
    """Serve the web UI"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Mister Controller</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px;
            background: #f5f5f5;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 10px 0;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .btn-pause { background: #ff9800; color: white; }
        .btn-resume { background: #4caf50; color: white; }
        .btn-stop { background: #f44336; color: white; }
        .btn-start { background: #2196f3; color: white; }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        .running { background: #4caf50; }
        .paused { background: #ff9800; }
        .stopped { background: #f44336; }
        .misting { background: #2196f3; }
        .temp-high { color: #f44336; font-weight: bold; }
        .humidity-low { color: #ff9800; font-weight: bold; }
        .comfortable { color: #4caf50; }
        .auto-refresh {
            font-size: 12px;
            color: #666;
            text-align: center;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <h1>🌡️ Server Shed Mister Controller</h1>
    
    <div class="card">
        <h2>System Status</h2>
        <div id="status-content">Loading...</div>
        <div class="auto-refresh">Auto-refreshing every 5 seconds</div>
    </div>
    
    <div class="card">
        <h2>Controls</h2>
        <div class="controls" id="controls">
            <button class="btn-pause" onclick="pauseController()">⏸️ Pause</button>
            <button class="btn-resume" onclick="resumeController()">▶️ Resume</button>
            <button class="btn-stop" onclick="stopController()">⏹️ Stop</button>
            <button class="btn-start" onclick="startController()">🚀 Start</button>
        </div>
    </div>
    
    <div class="card">
        <h2>Configuration</h2>
        <div id="config-content">Loading...</div>
    </div>

    <script>
        let lastUpdate = null;
        
        function formatTime(timeStr) {
            if (!timeStr) return 'Never';
            return new Date(timeStr).toLocaleString();
        }
        
        function formatDuration(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            if (mins > 0) return `${mins}m ${secs}s`;
            return `${secs}s`;
        }
        
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                let statusClass = 'stopped';
                let statusText = 'Stopped';
                
                if (data.is_running && data.is_paused) {
                    statusClass = 'paused';
                    statusText = 'Paused';
                } else if (data.is_running) {
                    statusClass = 'running';
                    statusText = 'Running';
                }
                
                let tempClass = 'comfortable';
                let humidityClass = 'comfortable';
                
                if (data.current_temp > data.config.temperature_threshold_high) {
                    tempClass = 'temp-high';
                }
                if (data.current_humidity < data.config.humidity_threshold_low) {
                    humidityClass = 'humidity-low';
                }
                
                const mistingStatus = data.is_misting ? 
                    '<span class="status-indicator misting"></span>MISTING ACTIVE' : 
                    'Standby';
                
                document.getElementById('status-content').innerHTML = `
                    <div class="status">
                        <strong>Controller:</strong>
                        <span><span class="status-indicator ${statusClass}"></span>${statusText}</span>
                    </div>
                    <div class="status">
                        <strong>Misting:</strong>
                        <span>${mistingStatus}</span>
                    </div>
                    <div class="status">
                        <strong>Temperature:</strong>
                        <span class="${tempClass}">${data.current_temp ? data.current_temp.toFixed(1) + '°F' : 'No data'}</span>
                    </div>
                    <div class="status">
                        <strong>Humidity:</strong>
                        <span class="${humidityClass}">${data.current_humidity ? data.current_humidity + '%' : 'No data'}</span>
                    </div>
                    <div class="status">
                        <strong>Last Reading:</strong>
                        <span>${formatTime(data.last_reading_time)}</span>
                    </div>
                    <div class="status">
                        <strong>Last Misting:</strong>
                        <span>${formatTime(data.last_mister_start)}</span>
                    </div>
                    <div class="status">
                        <strong>Uptime:</strong>
                        <span>${formatDuration(data.uptime_seconds)}</span>
                    </div>
                `;
                
                document.getElementById('config-content').innerHTML = `
                    <div class="status">
                        <strong>Start Misting:</strong>
                        <span>Temp > ${data.config.temperature_threshold_high}°F AND Humidity < ${data.config.humidity_threshold_low}%</span>
                    </div>
                    <div class="status">
                        <strong>Stop Misting:</strong>
                        <span>Temp < ${data.config.temperature_threshold_low}°F OR Humidity > ${data.config.humidity_threshold_high}%</span>
                    </div>
                    <div class="status">
                        <strong>Misting Duration:</strong>
                        <span>${formatDuration(data.config.mister_duration_seconds)}</span>
                    </div>
                    <div class="status">
                        <strong>Cooldown Period:</strong>
                        <span>${formatDuration(data.config.cooldown_seconds)}</span>
                    </div>
                    <div class="status">
                        <strong>Check Interval:</strong>
                        <span>${formatDuration(data.config.check_interval_seconds)}</span>
                    </div>
                `;
                
                lastUpdate = new Date().toLocaleString();
            } catch (error) {
                console.error('Failed to update status:', error);
                document.getElementById('status-content').innerHTML = 
                    '<div style="color: red;">Failed to load status</div>';
            }
        }
        
        async function sendControlCommand(action) {
            try {
                const response = await fetch(`/api/${action}`, { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    updateStatus();
                } else {
                    alert(`Failed to ${action}: ${data.message}`);
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }
        
        function pauseController() { sendControlCommand('pause'); }
        function resumeController() { sendControlCommand('resume'); }
        function stopController() { sendControlCommand('stop'); }
        function startController() { sendControlCommand('start'); }
        
        // Initial load and auto-refresh
        updateStatus();
        setInterval(updateStatus, 5000);
    </script>
</body>
</html>
    """

@app.get("/api/status")
async def get_status() -> StatusResponse:
    """Get current system status"""
    uptime = (datetime.now() - state.start_time).total_seconds()
    
    return StatusResponse(
        is_running=state.is_running,
        is_paused=state.is_paused,
        is_misting=state.is_misting,
        current_temp=state.last_reading.temperature if state.last_reading else None,
        current_humidity=state.last_reading.humidity if state.last_reading else None,
        last_reading_time=state.last_reading_time.isoformat() if state.last_reading_time else None,
        last_mister_start=state.last_mister_start.isoformat() if state.last_mister_start else None,
        uptime_seconds=int(uptime),
        config={
            "temperature_threshold_high": state.config.temperature_threshold_high,
            "temperature_threshold_low": state.config.temperature_threshold_low,
            "humidity_threshold_low": state.config.humidity_threshold_low,
            "humidity_threshold_high": state.config.humidity_threshold_high,
            "mister_duration_seconds": state.config.mister_duration_seconds,
            "check_interval_seconds": state.config.check_interval_seconds,
            "cooldown_seconds": state.config.cooldown_seconds
        }
    )

@app.post("/api/pause")
async def pause_controller() -> ControlResponse:
    """Pause the controller"""
    success, message = state.pause()
    return ControlResponse(
        success=success,
        message=message,
        new_status="paused" if success else ("running" if state.is_running else "stopped")
    )

@app.post("/api/resume")
async def resume_controller() -> ControlResponse:
    """Resume the controller"""
    success, message = state.resume()
    return ControlResponse(
        success=success,
        message=message,
        new_status="running" if success else ("paused" if state.is_paused else "stopped")
    )

@app.post("/api/stop")
async def stop_controller() -> ControlResponse:
    """Stop the controller"""
    success, message = state.stop()
    return ControlResponse(
        success=success,
        message=message,
        new_status="stopped"
    )

@app.post("/api/start")
async def start_controller() -> ControlResponse:
    """Start the controller"""
    success, message = state.start()
    return ControlResponse(
        success=success,
        message=message,
        new_status="running" if success else "stopped"
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")