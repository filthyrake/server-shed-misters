#!/usr/bin/env python3

import requests
import os

# Get credentials from environment variables
JS_RACHIO_API_KEY = os.environ.get("RACHIO_API_TOKEN")
JS_RACHIO_ZONE_ID = os.environ.get("RACHIO_ZONE_ID")  # Previously used person ID as zone ID

def test_js_credentials():
    if not JS_RACHIO_API_KEY:
        print("Error: RACHIO_API_TOKEN environment variable not set")
        return None, None
        
    headers = {
        "Authorization": f"Bearer {JS_RACHIO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("TESTING WITH JAVASCRIPT CREDENTIALS")
    print("=" * 60)
    print(f"API Key: {JS_RACHIO_API_KEY}")
    print(f"Zone ID: {JS_RACHIO_ZONE_ID}")
    
    # Test person info
    print("\n1. Testing person info...")
    response = requests.get("https://api.rach.io/1/public/person/info", headers=headers)
    
    if response.status_code == 200:
        person_info = response.json()
        person_id = person_info["id"]
        print(f"✓ Success! Person ID: {person_id}")
        
        # Get full person data
        print("\n2. Getting devices...")
        person_response = requests.get(f"https://api.rach.io/1/public/person/{person_id}", headers=headers)
        
        if person_response.status_code == 200:
            person_data = person_response.json()
            devices = person_data.get('devices', [])
            
            if devices:
                print(f"✓ Found {len(devices)} device(s):")
                
                for device in devices:
                    print(f"\n   Device: {device.get('name', 'Unnamed')}")
                    print(f"     ID: {device['id']}")
                    print(f"     Model: {device.get('model', 'Unknown')}")
                    
                    zones = device.get('zones', [])
                    enabled_zones = [z for z in zones if z.get('enabled')]
                    
                    if enabled_zones:
                        print(f"     Enabled zones ({len(enabled_zones)}):")
                        for zone in enabled_zones:
                            print(f"       - {zone.get('name', 'Unnamed')}")
                            print(f"         ID: {zone['id']}")
                        
                        # Test the first enabled zone
                        test_zone = enabled_zones[0]
                        print(f"\n3. Testing zone control...")
                        print(f"   Zone: {test_zone.get('name', 'Unnamed')}")
                        
                        test = input("   Start this zone for 5 seconds? (y/N): ").lower()
                        
                        if test == 'y':
                            url = "https://api.rach.io/1/public/zone/start"
                            data = {
                                "id": test_zone['id'],
                                "duration": 5
                            }
                            
                            print(f"   Starting zone {test_zone['id']} for 5 seconds...")
                            zone_response = requests.put(url, headers=headers, json=data)
                            
                            if zone_response.status_code == 204:
                                print("   ✓ ZONE STARTED SUCCESSFULLY!")
                                
                                print("\n" + "=" * 60)
                                print("WORKING CONFIGURATION:")
                                print("=" * 60)
                                print("Update your .env file with:")
                                print(f"RACHIO_API_TOKEN={JS_RACHIO_API_KEY}")
                                print(f"RACHIO_ZONE_ID={test_zone['id']}")
                                print(f"RACHIO_DEVICE_ID={device['id']}")
                                
                                return test_zone['id'], device['id']
                            else:
                                print(f"   ✗ Failed to start zone: {zone_response.status_code}")
                                print(f"   Response: {zone_response.text}")
                    else:
                        print("     No enabled zones")
            else:
                print("✗ No devices found")
        else:
            print(f"✗ Failed to get person data: {person_response.status_code}")
    else:
        print(f"✗ Failed to authenticate: {response.status_code}")
        print(f"  Response: {response.text[:200]}")
    
    return None, None


if __name__ == "__main__":
    zone_id, device_id = test_js_credentials()
    
    if zone_id and device_id:
        print("\n✓ SUCCESS! Your mister can now be controlled.")
    else:
        print("\n✗ Could not find working zone configuration.")
        print("\nNext steps:")
        print("1. Check if the API key in your JavaScript is still valid")
        print("2. Verify the device is set up in the Rachio app")
        print("3. Try generating a new API key at https://app.rach.io/")