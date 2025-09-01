#!/usr/bin/env python3

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def exhaustive_rachio_search():
    """Try every possible way to find your Rachio devices"""
    
    api_key = os.environ.get("RACHIO_API_TOKEN")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("EXHAUSTIVE RACHIO DEVICE SEARCH")
    print("=" * 60)
    
    # Get person info first
    person_response = requests.get("https://api.rach.io/1/public/person/info", headers=headers)
    if person_response.status_code != 200:
        print("Failed to get person info")
        return
    
    person_id = person_response.json()["id"]
    print(f"Person ID: {person_id}")
    
    # Try all possible API endpoints and versions
    base_urls = [
        "https://api.rach.io/1/public",
        "https://api.rach.io/1", 
        "https://api.rach.io/public",
        "https://cloud-rest.rach.io",
        "https://api.rach.io/2/public"
    ]
    
    endpoints_to_try = [
        # Traditional endpoints
        f"/person/{person_id}",
        "/devices",
        "/zones",
        
        # Smart Hose Timer endpoints
        f"/valve/listBaseStations/{person_id}",
        "/valve/listBaseStations",
        f"/smartHoseTimer/listBaseStations/{person_id}",
        "/smartHoseTimer/list",
        "/basestation/list",
        f"/basestation/listByUser/{person_id}",
        
        # Valve endpoints
        "/valve/list",
        f"/valve/listByUser/{person_id}",
        "/valves",
        f"/user/{person_id}/valves",
        
        # Generic device endpoints
        f"/user/{person_id}/devices",
        "/device/list",
        f"/device/listByUser/{person_id}"
    ]
    
    found_devices = []
    
    for base_url in base_urls:
        print(f"\nTrying base URL: {base_url}")
        
        for endpoint in endpoints_to_try:
            url = f"{base_url}{endpoint}"
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if data and (isinstance(data, list) and len(data) > 0 or 
                                   isinstance(data, dict) and any(key in data for key in ['devices', 'zones', 'valves', 'baseStations'])):
                            print(f"  ✓ SUCCESS: {endpoint}")
                            print(f"    Data preview: {json.dumps(data, indent=2)[:300]}...")
                            
                            # Look for anything that might be controllable
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and 'id' in item:
                                        found_devices.append({
                                            'endpoint': endpoint,
                                            'id': item['id'],
                                            'name': item.get('name', 'Unknown'),
                                            'type': item.get('type', item.get('deviceType', 'Unknown')),
                                            'data': item
                                        })
                            elif isinstance(data, dict):
                                # Check for devices in various fields
                                for field in ['devices', 'zones', 'valves', 'baseStations']:
                                    items = data.get(field, [])
                                    if isinstance(items, list):
                                        for item in items:
                                            if isinstance(item, dict) and 'id' in item:
                                                found_devices.append({
                                                    'endpoint': endpoint,
                                                    'field': field,
                                                    'id': item['id'],
                                                    'name': item.get('name', 'Unknown'),
                                                    'type': item.get('type', item.get('deviceType', 'Unknown')),
                                                    'data': item
                                                })
                        
                    except json.JSONDecodeError:
                        if len(response.text) < 100:
                            print(f"  ✓ SUCCESS: {endpoint} (non-JSON response: {response.text})")
                
                elif response.status_code == 404:
                    pass  # Expected for most endpoints
                else:
                    print(f"  ? {endpoint}: Status {response.status_code}")
                    
            except Exception as e:
                print(f"  ✗ {endpoint}: {str(e)[:50]}")
    
    print("\n" + "=" * 60)
    print("FOUND DEVICES SUMMARY")
    print("=" * 60)
    
    if found_devices:
        for i, device in enumerate(found_devices, 1):
            print(f"\n{i}. Device found via {device['endpoint']}")
            if 'field' in device:
                print(f"   Field: {device['field']}")
            print(f"   Name: {device['name']}")
            print(f"   ID: {device['id']}")
            print(f"   Type: {device['type']}")
            
            # Test if this device can be controlled
            print(f"   Testing control...")
            test_control_device(device['id'], headers)
    else:
        print("No devices found through any API endpoint")
        print("\nThis suggests:")
        print("1. Your Smart Hose Timer isn't fully registered with the API")
        print("2. The API access might be limited/beta")
        print("3. The device might need re-registration")


def test_control_device(device_id, headers):
    """Test if we can control a specific device"""
    
    # Test zone control
    zone_url = "https://api.rach.io/1/public/zone/start"
    zone_data = {"id": device_id, "duration": 1}
    
    response = requests.put(zone_url, headers=headers, json=zone_data)
    if response.status_code == 204:
        print("   ✓ ZONE CONTROL WORKS!")
        
        # Stop it immediately
        stop_data = {"id": device_id}
        requests.put("https://api.rach.io/1/public/device/stop_water", headers=headers, json=stop_data)
        
        print(f"\n   WORKING CONFIGURATION:")
        print(f"   RACHIO_ZONE_ID={device_id}")
        return True
    
    # Test valve control
    valve_url = "https://api.rach.io/1/public/valve/startWatering"
    valve_data = {"valveId": device_id, "durationSeconds": 1}
    
    response = requests.put(valve_url, headers=headers, json=valve_data)
    if response.status_code == 204:
        print("   ✓ VALVE CONTROL WORKS!")
        
        # Stop it
        stop_data = {"valveId": device_id}
        requests.put("https://api.rach.io/1/public/valve/stopWatering", headers=headers, json=stop_data)
        
        print(f"\n   WORKING CONFIGURATION:")
        print(f"   RACHIO_VALVE_ID={device_id}")
        return True
    
    print("   ✗ No control methods work")
    return False


if __name__ == "__main__":
    exhaustive_rachio_search()