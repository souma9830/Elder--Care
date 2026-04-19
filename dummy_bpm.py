import requests
import time
import random

API_BPM_URL = "http://127.0.0.1:5000/api/heartrate"

print("Starting Dummy IoT Simulator for Heart Rate...")
print("This will send fake BPM data to your backend every 2 seconds.")
print("Press Ctrl+C to stop.\n")

# Start at a normal resting heart rate
current_bpm = 72

try:
    while True:
        # Generate a realistic fluctuating heart rate
        # Randomly walk between 65 and 95
        change = random.choice([-2, -1, 0, 1, 2, 3])
        current_bpm += change
        
        if current_bpm < 60:
            current_bpm = 60
        elif current_bpm > 110:
            current_bpm = 110
            
        payload = {"bpm": current_bpm}
        
        try:
            response = requests.post(API_BPM_URL, json=payload, timeout=2)
            if response.status_code == 200:
                print(f"[SUCCESS] Sent Heart Rate: {current_bpm} BPM")
            else:
                print(f"[FAILED] Server responded with status code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("[ERROR] Could not connect to backend. Make sure 'app.py' is running!")
            
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\nDummy simulator stopped. Goodbye!")
