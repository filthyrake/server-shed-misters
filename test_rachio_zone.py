#!/usr/bin/env python3

import os
import requests
from dotenv import load_dotenv
import time

load_dotenv()

# Zone ID from environment variables (no fallback)
ZONE_ID_FROM_JS = os.environ.get("RACHIO_ZONE_ID")

def test_rachio_zone():
    rachio_token = os.environ.get("RACHIO_API_TOKEN")
    
    if not rachio_token:
        print("Missing RACHIO_API_TOKEN")
        return
        
    if not ZONE_ID_FROM_JS:
        print("Missing RACHIO_ZONE_ID")
        return
    
    headers = {
        "Authorization": f"Bearer {rachio_token}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("TESTING RACHIO ZONE CONTROL")
    print("=" * 60)
    
    # Test if the ID from your JavaScript is actually a zone ID
    print(f"\nTesting if {ZONE_ID_FROM_JS} is a zone ID...")
    
    # Try to start the zone for 5 seconds
    url = "https://api.rach.io/1/public/zone/start"
    data = {
        "id": ZONE_ID_FROM_JS,
        "duration": 5  # 5 seconds for testing
    }
    
    print(f"Attempting to start zone for 5 seconds...")
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code == 204:
        print("✓ SUCCESS! Zone started for 5 seconds")
        print("  The zone will stop automatically")
        return True
    else:
        print(f"✗ Failed: Status {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        
        # Try to get more info about this ID
        print("\nLet's check what this ID actually is...")
        
        # Check if it's a person ID
        person_url = f"https://api.rach.io/1/public/person/{ZONE_ID_FROM_JS}"
        person_response = requests.get(person_url, headers=headers)
        
        if person_response.status_code == 200:
            person_data = person_response.json()
            print(f"✓ This is a Person ID for: {person_data.get('username', 'Unknown')}")
            
            # Get their devices
            devices = person_data.get('devices', [])
            print(f"\nFound {len(devices)} device(s):")
            
            for device in devices:
                print(f"\n  Device: {device.get('name', 'Unnamed')}")
                print(f"    ID: {device['id']}")
                
                zones = device.get('zones', [])
                enabled_zones = [z for z in zones if z.get('enabled')]
                
                if enabled_zones:
                    print(f"    Zones ({len(enabled_zones)} enabled):")
                    for zone in enabled_zones:
                        print(f"      - {zone.get('name', 'Unnamed')}")
                        print(f"        ID: {zone['id']}")
                        print(f"        Zone Number: {zone.get('zoneNumber', 'N/A')}")
                        
                        # Save first zone for testing
                        if 'FIRST_ZONE' not in locals():
                            FIRST_ZONE = zone
                            
            if 'FIRST_ZONE' in locals():
                print("\n" + "=" * 60)
                print("TESTING WITH ACTUAL ZONE")
                print("=" * 60)
                
                test = input(f"\nTest zone '{FIRST_ZONE['name']}' for 5 seconds? (y/N): ").lower()
                if test == 'y':
                    data = {
                        "id": FIRST_ZONE['id'],
                        "duration": 5
                    }
                    
                    print(f"Starting zone {FIRST_ZONE['id']} for 5 seconds...")
                    response = requests.put(url, headers=headers, json=data)
                    
                    if response.status_code == 204:
                        print("✓ Zone started successfully!")
                        print("  It will stop automatically after 5 seconds")
                        
                        print("\n" + "=" * 60)
                        print("ADD THIS TO YOUR .ENV FILE:")
                        print("=" * 60)
                        print(f"RACHIO_ZONE_ID={FIRST_ZONE['id']}")
                        print(f"RACHIO_DEVICE_ID={device['id']}")
                    else:
                        print(f"✗ Failed: {response.status_code}")
        else:
            print(f"✗ Not a valid person ID either")


if __name__ == "__main__":
    test_rachio_zone()