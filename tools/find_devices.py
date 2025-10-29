#!/usr/bin/env python3

import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

def test_all_rachio_apis():
    rachio_token = os.environ.get("RACHIO_API_TOKEN")
    
    if not rachio_token:
        print("Missing RACHIO_API_TOKEN")
        return
    
    headers = {
        "Authorization": f"Bearer {rachio_token}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("COMPREHENSIVE RACHIO API TEST")
    print("=" * 60)
    
    # Get person info
    print("\n1. Getting Person Info...")
    response = requests.get("https://api.rach.io/1/public/person/info", headers=headers, timeout=(10, 30))
    
    if response.status_code == 200:
        person_info = response.json()
        person_id = person_info["id"]
        print(f"✓ Person ID: {person_id}")
        
        # Check for traditional controllers
        print("\n2. Checking for Traditional Controllers...")
        person_response = requests.get(f"https://api.rach.io/1/public/person/{person_id}", headers=headers, timeout=(10, 30))
        
        if person_response.status_code == 200:
            person_data = person_response.json()
            devices = person_data.get('devices', [])
            print(f"   Traditional controllers found: {len(devices)}")
            
            if devices:
                for device in devices:
                    print(f"   - {device.get('name', 'Unnamed')} ({device['id']})")
        
        # Now try Smart Hose Timer endpoints with different variations
        print("\n3. Checking for Smart Hose Timer (Base Stations)...")
        
        # Try different endpoint variations
        endpoints_to_try = [
            (f"https://api.rach.io/1/public/valve/listBaseStations/{person_id}", "GET", None),
            (f"https://api.rach.io/1/public/basestation/list", "GET", None),
            (f"https://api.rach.io/1/public/valve/getBaseStations", "POST", {"userId": person_id}),
            (f"https://cloud-rest.rach.io/valve/listBaseStations", "GET", None),
            (f"https://api.rach.io/1/public/smartHoseTimer/list", "GET", None),
        ]
        
        for url, method, data in endpoints_to_try:
            print(f"\n   Trying: {url}")
            
            try:
                if method == "GET":
                    resp = requests.get(url, headers=headers, timeout=(10, 30))
                else:
                    resp = requests.post(url, headers=headers, json=data, timeout=(10, 30))
                
                if resp.status_code == 200:
                    result = resp.json()
                    print(f"   ✓ SUCCESS! Found data:")
                    print(f"     {json.dumps(result, indent=2)[:500]}")
                    
                    # If we found base stations, try to get valves
                    if isinstance(result, list) and len(result) > 0:
                        for bs in result:
                            if 'id' in bs:
                                print(f"\n   Checking valves for base station {bs['id']}...")
                                valve_url = f"https://api.rach.io/1/public/valve/listValves/{bs['id']}"
                                valve_resp = requests.get(valve_url, headers=headers, timeout=(10, 30))
                                
                                if valve_resp.status_code == 200:
                                    valves = valve_resp.json()
                                    print(f"   ✓ Found {len(valves)} valve(s)")
                                    for valve in valves:
                                        print(f"     - {valve.get('name', 'Unnamed')} ({valve['id']})")
                    break
                elif resp.status_code == 404:
                    print(f"   ✗ 404 Not Found")
                else:
                    print(f"   ✗ Status {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                print(f"   ✗ Exception: {str(e)[:100]}")
        
        # Check if the account has valve permissions
        print("\n4. Checking Account Permissions...")
        
        # Try to access valve API documentation endpoint
        doc_urls = [
            "https://api.rach.io/1/public/valve",
            "https://api.rach.io/1/public/smartHoseTimer"
        ]
        
        for url in doc_urls:
            resp = requests.get(url, headers=headers, timeout=(10, 30))
            print(f"   {url}: Status {resp.status_code}")
    else:
        print(f"✗ Failed to get person info: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS:")
    print("=" * 60)
    print("\nIf you're not seeing your Smart Hose Timer, possible reasons:")
    print("1. The device needs to be set up in the Rachio app first")
    print("2. The API token might need to be regenerated after adding the device")
    print("3. Smart Hose Timer API might require special permissions")
    print("4. The device might take time to sync with the API")
    print("\nNext steps:")
    print("1. Open the Rachio app and confirm your Smart Hose Timer is working")
    print("2. Try manually starting/stopping it from the app")
    print("3. Generate a new API token at https://app.rach.io/")
    print("4. Contact Rachio support about API access for Smart Hose Timer")


if __name__ == "__main__":
    test_all_rachio_apis()