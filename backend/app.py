from flask import Flask, request, jsonify
from flask_cors import CORS
import time

# Import our new MongoDB Database Layer
from database import DatabaseLayer

app = Flask(__name__)
CORS(app)

# --- BPM Endpoint ---
@app.route('/api/heartrate', methods=['POST'])
def update_bpm():
    try:
        data = request.get_json()
        if 'bpm' in data:
            DatabaseLayer.update_bpm(data['bpm'])
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
        lid_open = data.get('lid_open')
        reminder = data.get('reminder_triggered')
        
        if lid_open is not None or reminder is not None:
            DatabaseLayer.update_medicine_state(lid_open, reminder)
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
            is_fall = data['is_fall']
            confidence = data.get('confidence', 0.0)
            
            # Read previous state BEFORE updating, to detect False→True transition
            prev_state = DatabaseLayer.get_full_state()
            was_falling = prev_state.get('is_fall', False)
            
            # Log raw metrics and update state
            debug_info = {k: v for k, v in data.items() if k not in ["is_fall", "confidence"]}
            DatabaseLayer.log_fall_frame(is_fall, confidence, debug_info)
            
            # Log event only on new fall (transition from not-fall to fall)
            if is_fall and not was_falling:
                DatabaseLayer.log_event("fall", "Fall detected by vision system", "critical")
                
            return jsonify({"status": "success"}), 200
        return jsonify({"error": "Invalid format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Dashboard State Polling ---
@app.route('/api/state', methods=['GET'])
def get_state():
    try:
        state = DatabaseLayer.get_full_state()
        return jsonify(state), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Medicine Schedule API ---
@app.route('/api/schedule', methods=['GET', 'POST'])
def handle_schedule():
    if request.method == 'GET':
        schedule = DatabaseLayer.get_schedule()
        return jsonify({"schedule": schedule}), 200
    
    # POST
    try:
        data = request.get_json()
        # Ensure 'schedule' list is passed
        schedule = data if isinstance(data, list) else data.get('schedule', [])
        DatabaseLayer.save_schedule(schedule)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Event Logging API ---
@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        events = DatabaseLayer.get_events(limit=60)
        return jsonify(events), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Listen on all interfaces so ESP32 can connect
    app.run(host='0.0.0.0', port=5000)
