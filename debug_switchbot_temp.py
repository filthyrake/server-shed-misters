#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from mister_controller import SwitchBotAPI
import json

load_dotenv()

def debug_temperature():
    switchbot_token = os.environ.get("SWITCHBOT_TOKEN")
    switchbot_secret = os.environ.get("SWITCHBOT_SECRET")
    hub2_device_id = os.environ.get("HUB2_DEVICE_ID")
    
    api = SwitchBotAPI(switchbot_token, switchbot_secret)
    
    print("=" * 60)
    print("DEBUGGING SWITCHBOT TEMPERATURE")
    print("=" * 60)
    
    # Get raw device status
    print(f"Hub 2 Device ID: {hub2_device_id}")
    
    raw_status = api.get_device_status(hub2_device_id)
    
    if raw_status:
        print("\nRaw API Response:")
        print(json.dumps(raw_status, indent=2))
        
        temp_raw = raw_status.get('temperature')
        humidity = raw_status.get('humidity')
        
        print(f"\nRaw temperature value: {temp_raw}")
        print(f"Raw humidity value: {humidity}")
        
        # The app shows 98.8°F, but we're getting 37.1
        # This suggests the API might be returning Celsius
        if temp_raw:
            temp_celsius = float(temp_raw)
            temp_fahrenheit = (temp_celsius * 9/5) + 32
            
            print(f"\nTemperature conversions:")
            print(f"  Raw value: {temp_raw}")
            print(f"  As Celsius: {temp_celsius}°C")
            print(f"  Converted to Fahrenheit: {temp_fahrenheit}°F")
            
            print(f"\nApp shows: 98.8°F")
            print(f"We calculated: {temp_fahrenheit}°F")
            
            if abs(temp_fahrenheit - 98.8) < 5:
                print("✓ Conversion looks correct!")
                return True
            else:
                print("✗ Conversion doesn't match app")
                
                # Maybe it's already in Fahrenheit but wrong?
                print(f"\nIf raw value is already Fahrenheit: {temp_raw}°F")
                
    else:
        print("✗ Failed to get device status")
    
    return False

if __name__ == "__main__":
    debug_temperature()