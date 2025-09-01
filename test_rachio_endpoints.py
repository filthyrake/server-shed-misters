#!/usr/bin/env python3

import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

rachio_token = os.environ.get("RACHIO_API_TOKEN")

if not rachio_token:
    print("Missing RACHIO_API_TOKEN")
    exit(1)

headers = {
    "Authorization": f"Bearer {rachio_token}",
    "Content-Type": "application/json"
}

print("Testing various Rachio API endpoints...")
print("=" * 60)

# Test endpoints
endpoints = [
    "/public/person/info",
    "/public/notification/webhook",
]

base_url = "https://api.rach.io/1"

for endpoint in endpoints:
    print(f"\nTesting {endpoint}...")
    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success: {json.dumps(data, indent=2)[:500]}...")
            
            # If we get person info, try to get full person data
            if endpoint == "/public/person/info" and "id" in data:
                person_id = data["id"]
                print(f"\nFetching full person data for ID: {person_id}")
                person_response = requests.get(f"{base_url}/public/person/{person_id}", headers=headers)
                if person_response.status_code == 200:
                    person_data = person_response.json()
                    # List all top-level keys
                    print("Person object contains these keys:")
                    for key in person_data.keys():
                        value = person_data[key]
                        if isinstance(value, list):
                            print(f"  - {key}: {len(value)} item(s)")
                        elif isinstance(value, dict):
                            print(f"  - {key}: {type(value).__name__}")
                        else:
                            print(f"  - {key}: {value}")
        else:
            print(f"✗ Error {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Exception: {e}")

# Try the Smart Hose Timer API
print("\n" + "=" * 60)
print("Testing Smart Hose Timer endpoints...")
print("=" * 60)

# Different base URL for cloud rest API
cloud_base = "https://cloud-rest.rach.io"
cloud_endpoints = [
    "/valve/listValves",
    "/smartHoseTimer/getSmartHoseTimers",
]

for endpoint in cloud_endpoints:
    print(f"\nTesting {endpoint}...")
    try:
        response = requests.get(f"{cloud_base}{endpoint}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success: {json.dumps(data, indent=2)[:500]}...")
        else:
            print(f"✗ Error {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Exception: {e}")