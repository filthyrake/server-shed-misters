#!/usr/bin/env python3

import os
import sys
import json
from dotenv import load_dotenv

# Add parent directory to path to import mister_controller
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mister_controller import SwitchBotAPI, RachioAPI

load_dotenv()

print("=" * 60)
print("Testing API Connections")
print("=" * 60)

# Test SwitchBot
print("\n1. TESTING SWITCHBOT API")
print("-" * 30)
switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
switchbot_secret = os.environ.get("SWITCHBOT_SECRET")

if switchbot_token and switchbot_secret:
    print("✓ SwitchBot credentials found")
    api = SwitchBotAPI(switchbot_token, switchbot_secret)
    
    print("Fetching devices...")
    devices = api.get_devices()
    
    if devices:
        print(f"✓ Found {len(devices)} device(s):\n")
        for device in devices:
            print(f"  - {device.get('deviceName', 'Unnamed')} ({device['deviceType']})")
            print(f"    ID: {device['deviceId']}")
            
            if device['deviceType'] == 'Hub 2':
                print("    → Testing Hub 2 status...")
                status = api.get_device_status(device['deviceId'])
                if status:
                    print(f"      Temperature: {status.get('temperature')}°F")
                    print(f"      Humidity: {status.get('humidity')}%")
    else:
        print("✗ Failed to get devices or no devices found")
else:
    print("✗ Missing SwitchBot credentials")

# Test Rachio
print("\n2. TESTING RACHIO API")
print("-" * 30)
rachio_token = os.environ.get("RACHIO_API_TOKEN")

if rachio_token:
    print("✓ Rachio token found")
    api = RachioAPI(rachio_token)
    
    print("Fetching person info...")
    person_info = api.get_person_info()
    
    if person_info:
        person_id = person_info.get("id")
        print(f"✓ Person ID: {person_id}")
        print(f"  Username: {person_info.get('username', 'N/A')}")
        
        print("\nFetching devices...")
        devices = api.get_devices(person_id)
        
        # Also check for valves
        print("\nChecking full person data for valves...")
        full_person = api._make_request(f"/person/{person_id}")
        if full_person:
            if 'smartHoseTimers' in full_person:
                print(f"Found smartHoseTimers: {full_person['smartHoseTimers']}")
            if 'valves' in full_person:
                print(f"Found valves: {full_person['valves']}")
        
        if devices:
            print(f"✓ Found {len(devices)} device(s):\n")
            for device in devices:
                print(f"  - {device.get('name', 'Unnamed')}")
                print(f"    ID: {device['id']}")
                print(f"    Model: {device.get('model', 'Unknown')}")
                
                zones = device.get('zones', [])
                enabled_zones = [z for z in zones if z.get('enabled')]
                
                if enabled_zones:
                    print(f"    Zones ({len(enabled_zones)} enabled):")
                    for zone in enabled_zones:
                        print(f"      - {zone.get('name', 'Unnamed')} (ID: {zone['id']})")
                else:
                    print("    No enabled zones")
        else:
            print("✗ No devices found")
    else:
        print("✗ Failed to get person info - check API token")
else:
    print("✗ Missing Rachio API token")

print("\n" + "=" * 60)
print("RECOMMENDED ENVIRONMENT VARIABLES:")
print("=" * 60)

hub2_id = os.environ.get("HUB2_DEVICE_ID", "")
zone_id = os.environ.get("RACHIO_ZONE_ID", "")
device_id = os.environ.get("RACHIO_DEVICE_ID", "")

if not hub2_id:
    print("# Add to your .env file:")
    print("HUB2_DEVICE_ID=<copy the Hub 2 device ID from above>")

if not zone_id:
    print("RACHIO_ZONE_ID=<copy the zone ID you want to control>")
    
if not device_id:
    print("RACHIO_DEVICE_ID=<copy the Rachio device ID from above>")