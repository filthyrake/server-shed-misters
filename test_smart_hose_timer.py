#!/usr/bin/env python3

import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

class RachioSmartHoseTimerAPI:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.rach.io/1/public"
        
    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None):
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            else:
                response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None
    
    def get_person_id(self):
        result = self._make_request("/person/info")
        if result:
            return result.get("id")
        return None
    
    def list_base_stations(self, user_id: str):
        return self._make_request(f"/valve/listBaseStations/{user_id}")
    
    def list_valves(self, base_station_id: str):
        return self._make_request(f"/valve/listValves/{base_station_id}")
    
    def start_watering(self, valve_id: str, duration_seconds: int):
        data = {
            "valveId": valve_id,
            "durationSeconds": duration_seconds
        }
        return self._make_request("/valve/startWatering", method="PUT", data=data)
    
    def stop_watering(self, valve_id: str):
        data = {
            "valveId": valve_id
        }
        return self._make_request("/valve/stopWatering", method="PUT", data=data)


def main():
    rachio_token = os.environ.get("RACHIO_API_TOKEN")
    
    if not rachio_token:
        print("Missing RACHIO_API_TOKEN")
        return
    
    api = RachioSmartHoseTimerAPI(rachio_token)
    
    print("=" * 60)
    print("RACHIO SMART HOSE TIMER TEST")
    print("=" * 60)
    
    # Get person ID
    person_id = api.get_person_id()
    if person_id:
        print(f"✓ Person ID: {person_id}")
        
        # List base stations
        print("\nFetching Base Stations...")
        base_stations = api.list_base_stations(person_id)
        
        if base_stations:
            print(f"✓ Found {len(base_stations)} base station(s):")
            
            for bs in base_stations:
                print(f"\n  Base Station: {bs.get('name', 'Unnamed')}")
                print(f"    ID: {bs['id']}")
                print(f"    Status: {bs.get('status', 'Unknown')}")
                
                # List valves for this base station
                print(f"\n    Fetching valves for base station {bs['id']}...")
                valves = api.list_valves(bs['id'])
                
                if valves:
                    print(f"    ✓ Found {len(valves)} valve(s):")
                    for valve in valves:
                        print(f"\n      Valve: {valve.get('name', 'Unnamed')}")
                        print(f"        ID: {valve['id']}")
                        print(f"        State: {valve.get('state', {}).get('state', 'Unknown')}")
                        print(f"        Default Runtime: {valve.get('defaultRuntimeSeconds', 0)} seconds")
                        
                        # Save the first valve ID for testing
                        if 'FIRST_VALVE_ID' not in locals():
                            FIRST_VALVE_ID = valve['id']
                            FIRST_BASE_STATION_ID = bs['id']
                else:
                    print("    ✗ No valves found for this base station")
        else:
            print("✗ No base stations found")
            print("\nMake sure your Smart Hose Timer is:")
            print("1. Set up in the Rachio app")
            print("2. Connected to WiFi")
            print("3. Associated with your account")
    else:
        print("✗ Failed to get person ID")
    
    # Print recommended .env variables
    if 'FIRST_VALVE_ID' in locals():
        print("\n" + "=" * 60)
        print("ADD THESE TO YOUR .ENV FILE:")
        print("=" * 60)
        print(f"RACHIO_BASE_STATION_ID={FIRST_BASE_STATION_ID}")
        print(f"RACHIO_VALVE_ID={FIRST_VALVE_ID}")
        
        # Test manual watering
        print("\n" + "=" * 60)
        print("TESTING MANUAL WATERING (5 seconds)")
        print("=" * 60)
        
        test = input("Test watering for 5 seconds? (y/N): ").lower()
        if test == 'y':
            print(f"Starting valve {FIRST_VALVE_ID} for 5 seconds...")
            result = api.start_watering(FIRST_VALVE_ID, 5)
            if result:
                print("✓ Watering started successfully!")
                print("  (It will stop automatically after 5 seconds)")
            else:
                print("✗ Failed to start watering")


if __name__ == "__main__":
    main()