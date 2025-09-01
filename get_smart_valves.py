#!/usr/bin/env python3

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def get_smart_hose_valves():
    """Get valves from the Smart Hose Timer base station we found"""
    
    api_key = os.environ.get("RACHIO_API_TOKEN")
    base_station_id = "REDACTED_BASE_STATION_ID"  # From previous search
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("GETTING SMART HOSE TIMER VALVES")
    print("=" * 60)
    print(f"Base Station ID: {base_station_id}")
    
    # Try the valve list endpoint for this base station
    valve_url = f"https://cloud-rest.rach.io/valve/listValves/{base_station_id}"
    
    print(f"\nFetching valves from: {valve_url}")
    
    response = requests.get(valve_url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print("✓ SUCCESS!")
        print(f"Raw response: {json.dumps(data, indent=2)}")
        
        valves = data.get('valves', []) if isinstance(data, dict) else data
        
        if valves and isinstance(valves, list):
            print(f"\nFound {len(valves)} valve(s):")
            
            for i, valve in enumerate(valves, 1):
                valve_id = valve.get('id')
                valve_name = valve.get('name', f'Valve {i}')
                
                print(f"\n{i}. {valve_name}")
                print(f"   ID: {valve_id}")
                print(f"   State: {valve.get('state', {}).get('state', 'Unknown')}")
                
                if valve_id:
                    print(f"   Testing valve control...")
                    
                    # Test Smart Hose Timer valve control
                    test_url = "https://cloud-rest.rach.io/valve/startWatering"
                    test_data = {
                        "valveId": valve_id,
                        "durationSeconds": 5
                    }
                    
                    test_response = requests.put(test_url, headers=headers, json=test_data)
                    
                    if test_response.status_code in [200, 204]:
                        print("   ✓ VALVE CONTROL WORKS!")
                        
                        # Stop it immediately  
                        stop_url = "https://cloud-rest.rach.io/valve/stopWatering"
                        stop_data = {"valveId": valve_id}
                        requests.put(stop_url, headers=headers, json=stop_data)
                        
                        print(f"\n" + "=" * 60)
                        print("WORKING SMART HOSE TIMER FOUND!")
                        print("=" * 60)
                        print("Add these to your .env file:")
                        print(f"RACHIO_BASE_STATION_ID={base_station_id}")
                        print(f"RACHIO_VALVE_ID={valve_id}")
                        print(f"# Base station: Hose timers")
                        print(f"# Valve: {valve_name}")
                        
                        return valve_id, base_station_id
                    else:
                        print(f"   ✗ Control failed: {test_response.status_code}")
                        print(f"   Response: {test_response.text}")
        else:
            print("No valves found in response")
    else:
        print(f"✗ Failed to get valves: {response.status_code}")
        print(f"Response: {response.text}")
    
    return None, None

if __name__ == "__main__":
    valve_id, base_station_id = get_smart_hose_valves()
    
    if valve_id:
        print("\n✓ SUCCESS! Your Smart Hose Timer can be controlled via API.")
    else:
        print("\n✗ Could not find or control valves.")
        print("The base station was found but no controllable valves were detected.")
        print("Check that your valve is:")
        print("1. Properly paired with the base station") 
        print("2. Online and responsive in the Rachio app")