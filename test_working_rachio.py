#!/usr/bin/env python3

import os
import requests
from dotenv import load_dotenv
import time

load_dotenv()

def find_working_zone():
    """Test the Rachio API the same way the JavaScript does"""
    
    # Your JavaScript shows this API key and zone ID work
    # Let's test them directly first
    rachio_token = os.environ.get("RACHIO_API_TOKEN")
    
    if not rachio_token:
        print("Missing RACHIO_API_TOKEN")
        return
    
    headers = {
        "Authorization": f"Bearer {rachio_token}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("TESTING RACHIO LIKE YOUR WORKING JAVASCRIPT")
    print("=" * 60)
    
    # First, get person info to find devices
    print("\n1. Getting your account info...")
    response = requests.get("https://api.rach.io/1/public/person/info", headers=headers)
    
    if response.status_code == 200:
        person_info = response.json()
        person_id = person_info["id"]
        print(f"✓ Person ID: {person_id}")
        
        # Get full person data including devices
        print("\n2. Getting your devices...")
        person_response = requests.get(f"https://api.rach.io/1/public/person/{person_id}", headers=headers)
        
        if person_response.status_code == 200:
            person_data = person_response.json()
            
            # Check ALL fields for any device-related data
            print("\n3. Checking all available data...")
            for key in person_data.keys():
                value = person_data[key]
                if isinstance(value, list) and len(value) > 0:
                    print(f"   Found {key}: {len(value)} items")
                    
                    # If it looks like it might be device-related, investigate
                    if 'device' in key.lower() or 'valve' in key.lower() or 'zone' in key.lower() or 'timer' in key.lower():
                        print(f"     Investigating {key}...")
                        for item in value:
                            if isinstance(item, dict):
                                print(f"       - {item.get('name', item.get('id', 'Unknown'))}")
            
            # Traditional devices
            devices = person_data.get('devices', [])
            
            # Maybe there's a different field for Smart Hose Timer?
            smart_timers = person_data.get('smartHoseTimers', [])
            valves = person_data.get('valves', [])
            base_stations = person_data.get('baseStations', [])
            
            if smart_timers:
                print(f"\n✓ Found {len(smart_timers)} Smart Hose Timer(s)")
                for timer in smart_timers:
                    print(f"   - {timer}")
            
            if valves:
                print(f"\n✓ Found {len(valves)} valve(s)")
                for valve in valves:
                    print(f"   - {valve}")
            
            if base_stations:
                print(f"\n✓ Found {len(base_stations)} base station(s)")
                for bs in base_stations:
                    print(f"   - {bs}")
            
            if devices:
                print(f"\n✓ Found {len(devices)} traditional device(s)")
                for device in devices:
                    print(f"   Device: {device.get('name', 'Unknown')}")
                    print(f"     ID: {device['id']}")
                    
                    zones = device.get('zones', [])
                    if zones:
                        for zone in zones:
                            if zone.get('enabled'):
                                print(f"     Zone: {zone.get('name', 'Unknown')}")
                                print(f"       ID: {zone['id']}")
                                print(f"       Enabled: {zone.get('enabled')}")
                                
                                # Test this zone
                                print(f"\n4. Testing zone control for '{zone.get('name')}'...")
                                test = input("   Test this zone for 5 seconds? (y/N): ").lower()
                                
                                if test == 'y':
                                    url = "https://api.rach.io/1/public/zone/start"
                                    data = {
                                        "id": zone['id'],
                                        "duration": 5
                                    }
                                    
                                    print(f"   Starting zone {zone['id']} for 5 seconds...")
                                    zone_response = requests.put(url, headers=headers, json=data)
                                    
                                    if zone_response.status_code == 204:
                                        print("   ✓ SUCCESS! Zone started!")
                                        print("\n" + "=" * 60)
                                        print("WORKING CONFIGURATION FOUND!")
                                        print("=" * 60)
                                        print("Add these to your .env file:")
                                        print(f"RACHIO_ZONE_ID={zone['id']}")
                                        print(f"RACHIO_DEVICE_ID={device['id']}")
                                        return zone['id'], device['id']
                                    else:
                                        print(f"   ✗ Failed: {zone_response.status_code}")
            else:
                print("\n✗ No devices found on this account")
                print("\nYour JavaScript code suggests there should be a zone that can be controlled.")
                print("The zone ID in your JS was actually your person ID.")
                print("\nPossible issues:")
                print("1. The Rachio device might be on a different account")
                print("2. The API token might not have the right permissions")
                print("3. The device might need to be shared with this account")
    else:
        print(f"✗ Failed to get person info: {response.status_code}")
    
    return None, None


if __name__ == "__main__":
    zone_id, device_id = find_working_zone()
    
    if not zone_id:
        print("\n" + "=" * 60)
        print("NO CONTROLLABLE ZONES FOUND")
        print("=" * 60)
        print("\nThe issue is that your Rachio account shows no devices.")
        print("But your JavaScript code works, which means either:")
        print("1. The device is on a different Rachio account")
        print("2. You need to regenerate your API token after adding the device")
        print("3. The device needs to be properly shared with your account")
        print("\nPlease check:")
        print("- Log into https://app.rach.io with the same credentials")
        print("- Verify you can see and control your device there")
        print("- Generate a fresh API token")
        print("- Update the RACHIO_API_TOKEN in your .env file")