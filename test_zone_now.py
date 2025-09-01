#!/usr/bin/env python3

import requests
import os

# Get credentials from environment variables
JS_RACHIO_API_KEY = os.environ.get("RACHIO_API_TOKEN")
JS_ZONE_ID = os.environ.get("RACHIO_ZONE_ID")

def test_zone_now():
    if not JS_RACHIO_API_KEY:
        print("Error: RACHIO_API_TOKEN environment variable not set")
        return False
        
    headers = {
        "Authorization": f"Bearer {JS_RACHIO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print("Testing zone control with your JavaScript credentials...")
    print(f"Zone ID: {JS_ZONE_ID}")
    
    url = "https://api.rach.io/1/public/zone/start"
    data = {
        "id": JS_ZONE_ID,
        "duration": 5
    }
    
    response = requests.put(url, headers=headers, json=data)
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Text: {response.text}")
    
    if response.status_code == 204:
        print("✓ SUCCESS! Zone started!")
        return True
    elif response.status_code == 412:
        print("✗ Zone not found")
        return False
    else:
        print("✗ Other error")
        return False

if __name__ == "__main__":
    success = test_zone_now()
    
    if success:
        print("\nYour JavaScript credentials work! I'll update the controller.")
    else:
        print("\nThe zone ID from your JavaScript doesn't work directly.")
        print("This suggests it might be controlling a different type of device")
        print("or the zone ID has changed since your JavaScript was written.")