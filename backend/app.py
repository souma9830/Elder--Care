from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import json
import os

app = Flask(__name__)
CORS(app)

# We will store the state in memory for now, but in reality we might want 
# to save some of this to a local db or file.
DATA_FILE = "data/medicines.json"
EVENTS_FILE = "data/events.json"

if not os.path.exists("data"):
    os.makedirs("data")

# In-memory system state
system_state = {
    "bpm": 0,
    "last_bpm_time": 0,
    "is_fall": False,
    "last_fall_time": 0,
    "lid_open": False,
    "reminder_triggered": False,
    "last_medicine_time": 0
}

# --- BPM Endpoint ---
@app.route('/api/heartrate', methods=['POST'])
def update_bpm():
    try:
        data = request.get_json()
        if 'bpm' in data:
            system_state['bpm'] = data['bpm']
            system_state['last_bpm_time'] = time.time()
            return jsonify({"status": "success", "bpm": data['bpm']}), 200
        return jsonify({"error": "Invalid format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Medicine Box Endpoint ---
@app.route('/api/medicine', methods=['POST'])
def update_medicine():
    try:
        data = request.get_json()
        updated = False
        if 'lid_open' in data:
            system_state['lid_open'] = data['lid_open']
            updated = True
        if 'reminder_triggered' in data:
            system_state['reminder_triggered'] = data['reminder_triggered']
            updated = True
        
        if updated:
            system_state['last_medicine_time'] = time.time()
            return jsonify({"status": "success", "state": data}), 200
        return jsonify({"error": "No valid fields"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Fall Detection Endpoint ---
@app.route('/api/fall', methods=['POST'])
def update_fall():
    try:
        data = request.get_json()
        if 'is_fall' in data:
            for k, v in data.items():
                system_state[k] = v
            system_state['last_fall_time'] = time.time()
            if data['is_fall']:
                # Save event to logs
                _log_event("fall", "Fall detected by vision system", "critical")
            return jsonify({"status": "success"}), 200
        return jsonify({"error": "Invalid format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Dashboard State Polling ---
@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(system_state), 200

# --- Medicine Schedule API ---
@app.route('/api/schedule', methods=['GET', 'POST'])
def handle_schedule():
    if request.method == 'GET':
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    return jsonify(json.load(f)), 200
            except:
                pass
        return jsonify({"schedule": ["08:00", "14:00", "20:00"]}), 200
    
    # POST
    try:
        data = request.get_json()
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
# --- Event Logging API ---
def _log_event(type, message, severity):
    event = {
        "type": type,
        "message": message,
        "severity": severity,
        "timestamp": time.time()
    }
    history = []
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, 'r') as f:
                 history = json.load(f)
        except:
            history = []
    
    history.insert(0, event)
    if len(history) > 60:
        history = history[:60]
        
    with open(EVENTS_FILE, 'w') as f:
        json.dump(history, f)
        
@app.route('/api/events', methods=['GET'])
def get_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, 'r') as f:
                 return jsonify(json.load(f)), 200
        except:
            pass
    return jsonify([]), 200

if __name__ == '__main__':
    # Listen on all interfaces so ESP32 can connect
    app.run(host='0.0.0.0', port=5000)
    
