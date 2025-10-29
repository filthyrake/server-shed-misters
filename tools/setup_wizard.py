#!/usr/bin/env python3

"""
DEPRECATED: This tool is for traditional Rachio controllers, not Smart Hose Timer.

This system only supports Rachio Smart Hose Timer (not traditional controllers).
For device discovery, use: tools/find_devices.py

This file is kept for reference purposes only.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import mister_controller
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Note: RachioAPI class has been removed as it's not used in production
# This tool would need to be updated to use SmartHoseTimerAPI for Smart Hose Timer support
print("=" * 70)
print("DEPRECATED TOOL")
print("=" * 70)
print("This tool is for traditional Rachio controllers, not Smart Hose Timer.")
print("The system now only supports Rachio Smart Hose Timer.")
print()
print("For device discovery, please use: tools/find_devices.py")
print("For setup verification, manually create .env based on .env.example")
print("=" * 70)
sys.exit(1)

def setup_environment():
    print("Server Shed Mister Controller - Setup Wizard")
    print("=" * 50)
    
    env_file = Path(".env")
    
    if env_file.exists():
        overwrite = input(".env file already exists. Overwrite? (y/N): ").lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
    
    print("\n1. SwitchBot Configuration")
    print("-" * 30)
    print("Get these from SwitchBot app (v6.14+) → Profile → Preferences")
    switchbot_token = input("Enter SwitchBot Token: ").strip()
    switchbot_secret = input("Enter SwitchBot Secret: ").strip()
    
    print("\n2. Rachio Configuration")
    print("-" * 30)
    print("Get this from https://app.rach.io/ → Account Settings → GET API KEY")
    rachio_token = input("Enter Rachio API Token: ").strip()
    
    print("\n3. Testing API Connections...")
    print("-" * 30)
    
    hub2_device_id = ""
    rachio_zone_id = ""
    rachio_device_id = ""
    
    try:
        switchbot_api = SwitchBotAPI(switchbot_token, switchbot_secret)
        devices = switchbot_api.get_devices()
        
        if devices:
            print("✓ SwitchBot API connected successfully")
            hub2_devices = [d for d in devices if d.get("deviceType") == "Hub 2"]
            
            if hub2_devices:
                print(f"\nFound {len(hub2_devices)} Hub 2 device(s):")
                for i, device in enumerate(hub2_devices):
                    print(f"  {i+1}. {device.get('deviceName', 'Unnamed')} ({device['deviceId']})")
                
                if len(hub2_devices) == 1:
                    hub2_device_id = hub2_devices[0]["deviceId"]
                    print(f"Auto-selected: {hub2_devices[0].get('deviceName', hub2_device_id)}")
                else:
                    choice = input("Select Hub 2 device number: ").strip()
                    try:
                        idx = int(choice) - 1
                        hub2_device_id = hub2_devices[idx]["deviceId"]
                    except (ValueError, IndexError):
                        print("Invalid selection, will need manual configuration")
            else:
                print("⚠ No Hub 2 devices found. Check SwitchBot app.")
        else:
            print("✗ Failed to connect to SwitchBot API. Check credentials.")
    except Exception as e:
        print(f"✗ SwitchBot API error: {e}")
    
    try:
        rachio_api = RachioAPI(rachio_token)
        person_id = rachio_api.get_person_id()
        
        if person_id:
            print("✓ Rachio API connected successfully")
            devices = rachio_api.get_devices(person_id)
            
            if devices:
                print(f"\nFound {len(devices)} Rachio device(s):")
                for i, device in enumerate(devices):
                    print(f"  {i+1}. {device.get('name', 'Unnamed')} ({device['id']})")
                
                if len(devices) == 1:
                    rachio_device_id = devices[0]["id"]
                    print(f"Auto-selected: {devices[0].get('name', rachio_device_id)}")
                    
                    zones = devices[0].get("zones", [])
                    enabled_zones = [z for z in zones if z.get("enabled")]
                    
                    if enabled_zones:
                        print(f"\nFound {len(enabled_zones)} enabled zone(s):")
                        for i, zone in enumerate(enabled_zones):
                            print(f"  {i+1}. {zone.get('name', 'Unnamed')} ({zone['id']})")
                        
                        if len(enabled_zones) == 1:
                            rachio_zone_id = enabled_zones[0]["id"]
                            print(f"Auto-selected: {enabled_zones[0].get('name', rachio_zone_id)}")
                        else:
                            choice = input("Select zone number for mister: ").strip()
                            try:
                                idx = int(choice) - 1
                                rachio_zone_id = enabled_zones[idx]["id"]
                            except (ValueError, IndexError):
                                print("Invalid selection, will need manual configuration")
                else:
                    choice = input("Select Rachio device number: ").strip()
                    try:
                        idx = int(choice) - 1
                        rachio_device_id = devices[idx]["id"]
                    except (ValueError, IndexError):
                        print("Invalid selection, will need manual configuration")
            else:
                print("⚠ No Rachio devices found. Check Rachio app.")
        else:
            print("✗ Failed to connect to Rachio API. Check token.")
    except Exception as e:
        print(f"✗ Rachio API error: {e}")
    
    print("\n4. Threshold Configuration")
    print("-" * 30)
    
    temp_high = input("Temperature HIGH threshold (°F) [95]: ").strip() or "95"
    temp_low = input("Temperature LOW threshold (°F) [95]: ").strip() or "95"
    humidity_low = input("Humidity LOW threshold (%) [35]: ").strip() or "35"
    humidity_high = input("Humidity HIGH threshold (%) [35]: ").strip() or "35"
    
    print("\n5. Timing Configuration")
    print("-" * 30)
    
    mister_duration = input("Mister run duration (seconds) [600]: ").strip() or "600"
    check_interval = input("Sensor check interval (seconds) [60]: ").strip() or "60"
    cooldown = input("Cooldown between runs (seconds) [300]: ").strip() or "300"
    
    env_content = f"""# SwitchBot API Credentials
SWITCHBOT_TOKEN={switchbot_token}
SWITCHBOT_SECRET={switchbot_secret}

# Rachio API Credentials
RACHIO_API_TOKEN={rachio_token}

# Device IDs
HUB2_DEVICE_ID={hub2_device_id}
RACHIO_ZONE_ID={rachio_zone_id}
RACHIO_DEVICE_ID={rachio_device_id}

# Temperature thresholds (in Fahrenheit)
TEMP_HIGH={temp_high}
TEMP_LOW={temp_low}

# Humidity thresholds (in percentage)
HUMIDITY_LOW={humidity_low}
HUMIDITY_HIGH={humidity_high}

# Mister operation settings
MISTER_DURATION={mister_duration}
CHECK_INTERVAL={check_interval}
COOLDOWN_SECONDS={cooldown}
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("\n✓ Configuration saved to .env")
    print("\nTo start the controller, run:")
    print("  python mister_controller.py")
    
    if not hub2_device_id or not rachio_zone_id:
        print("\n⚠ Some devices couldn't be auto-detected.")
        print("  Edit .env file manually with correct device IDs.")


if __name__ == "__main__":
    setup_environment()