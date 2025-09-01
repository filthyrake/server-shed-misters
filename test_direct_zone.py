#!/usr/bin/env python3

import requests
import os

# Get credentials from environment variables
JS_RACHIO_API_KEY = os.environ.get("RACHIO_API_TOKEN")
JS_ZONE_ID = os.environ.get("RACHIO_ZONE_ID")

def test_direct_zone_control():
    if not JS_RACHIO_API_KEY:
        print("Error: RACHIO_API_TOKEN environment variable not set")
        return False
        
    headers = {
        "Authorization": f"Bearer {JS_RACHIO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("TESTING DIRECT ZONE CONTROL (FROM YOUR JAVASCRIPT)")
    print("=" * 60)
    print(f"API Key: {JS_RACHIO_API_KEY}")
    print(f"Zone ID: {JS_ZONE_ID}")
    
    print("\nYour JavaScript uses this exact configuration to control watering.")
    print("Let's test if it works...")
    
    test = input("\nStart watering for 5 seconds using your JS config? (y/N): ").lower()
    
    if test == 'y':
        url = "https://api.rach.io/1/public/zone/start"
        data = {
            "id": JS_ZONE_ID,
            "duration": 5
        }
        
        print(f"\nStarting zone {JS_ZONE_ID} for 5 seconds...")
        response = requests.put(url, headers=headers, json=data)
        
        if response.status_code == 204:
            print("✓ SUCCESS! Zone started!")
            print("  Your JavaScript configuration works!")
            
            print("\n" + "=" * 60)
            print("WORKING CONFIGURATION FOUND!")
            print("=" * 60)
            print("Update your .env file with:")
            print(f"RACHIO_API_TOKEN={JS_RACHIO_API_KEY}")
            print(f"RACHIO_ZONE_ID={JS_ZONE_ID}")
            print(f"RACHIO_DEVICE_ID={JS_ZONE_ID}")  # Use same ID for device
            
            return True
        elif response.status_code == 412:
            print(f"✗ Zone not found (412): {response.text}")
            print("  The zone ID from your JavaScript doesn't exist")
        else:
            print(f"✗ Failed ({response.status_code}): {response.text}")
    
    print("\n" + "=" * 60)
    print("ALTERNATIVE APPROACH")
    print("=" * 60)
    print("Since your JavaScript works but we can't replicate it,")
    print("let's create a hybrid solution that:")
    print("1. Monitors SwitchBot sensors with Python")
    print("2. Triggers your existing JavaScript when misting is needed")
    print("\nThis would work by:")
    print("- Python script monitors temp/humidity every minute")
    print("- When conditions are met, it calls your n8n workflow")
    print("- Your n8n workflow uses the working JavaScript to activate Rachio")
    
    return False


if __name__ == "__main__":
    success = test_direct_zone_control()
    
    if not success:
        print("\nWould you like me to create the hybrid solution?")
        print("It will use your working JavaScript for Rachio control.")