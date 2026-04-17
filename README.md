# ElderCare Automation System

A comprehensive IoT and AI-powered system designed to assist with monitoring the well-being and medication adherence of elderly individuals. It consists of multiple modules running seamlessly together via a centralized MongoDB backend.

## Features

1. **Vision-based Fall Detection** 
   - Uses a webcam and MediaPipe Tasks API to analyze torso angle and bounding box aspect ratios to detect falls in real-time.
   - Throttled REST API updates to prevent network flood.
   - Triggers Gmail notifications (if configured).

2. **IoT Integration (ESP32)**
   - Expects REST endpoints for hardware connections checking heart-rate (BPM) and medicine box status (Lid open/close).

3. **Real-time Live Dashboard**
   - Beautiful localized dashboard syncing every 1.5 seconds.
   - Displays historic falls, current torso angle, FPS, heart-rate state, next medication doses, and total alerts all in real-time from the database.

4. **AI Voice Assistant**
   - Responds to audible triggers and fetches live hardware logs directly using the shared API to give vocal status updates regarding patient well-being and upcoming medicine schedules.

---

## 🛠️ Prerequisites & Setup

### 1. Database Setup
The entire system state, telemetry events, and configuration schedules operate exclusively on a local **MongoDB database**.
- Download and install [MongoDB Community Edition](https://www.mongodb.com/try/download/community).
- Ensure MongoDB is running locally on port `27017` (default).

### 2. Python Environment Setup
This system uses older libraries (like `pyttsx3` and legacy mediapipe dependencies for the voice modules), and thus strictly requires **Python 3.11**.
- Verify you have Python 3.11 installed. If not, download and install it.
- Open your terminal and install the required PIP dependencies.

```powershell
# We assume you have the py launcher installed on Windows
py -3.11 -m pip install -r requirements.txt
```
*(If you do not have a requirements.txt file, ensure at least the following are installed via pip: `flask flask-cors pymongo requests mediapipe opencv-python pyttsx3 numpy`)*

### 3. Model Download
The Fall Detector requires the Heavy Pose Landmarker model to function.
- Download the model from the official mediapipe repository: [pose_landmarker_heavy.task](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task).
- Place the downloaded file directly inside the `vision/` directory.

---

## 🚀 Running the System

To launch the full suite, simply double-click the `start_system.bat` file, or open a Command Prompt / PowerShell in the root directory and run:

```powershell
.\start_system.bat
```

This batch file will boot 4 separate command windows sequentially:
1. `backend/app.py` - Starts the central Flask API Server locally (port 5000), connecting to MongoDB.
2. `ai_assistant/assistant.py` - Starts the background voice module.
3. `vision/fall_detector.py` - Initiates the camera and MediaPipe engine to monitor falls.
4. Opens `dashboard/index.html` in your default web browser for the Real-time UI.

---

## 📡 Connecting External IoT Hardware

If you are using ESP32 hardware to track BPM or Medicine Box state, ensure it is connected to the same Wi-Fi network as the machine running the system.

In your Arduino code, point your `HTTPClient` to make POST requests to the backend server.
Assuming the computer running the backend has the local IP Address `192.168.1.50`:

**BPM Endpoint** (`POST http://192.168.1.50:5000/api/heartrate`)
```json
{
  "bpm": 72
}
```

**Medicine Box Endpoint** (`POST http://192.168.1.50:5000/api/medicine`)
```json
{
  "lid_open": true,
  "reminder_triggered": false
}
```

*Note: If your friend is using a different Wi-Fi connection from a separate house for the IoT, you will have to use Ngrok or render.com to expose this local `5000` port to the public internet.*

---

## 📩 Configuring Email Alerts 

If you want the Fall Detector to send emergency emails upon detecting a fall, you must configure a Gmail App Password.
1. Open `vision/fall_detector.py`
2. Change `GMAIL_ENABLED = False` to `GMAIL_ENABLED = True`
3. Enter your email in `GMAIL_SENDER` and `GMAIL_RECIPIENTS`
4. Provide a 16-character **App Password** for `GMAIL_APP_PASSWORD` (Generate this by going to Google Account Settings -> Security -> 2-Step Verification -> App Passwords).

---

## Troubleshooting

- **Black Screen / Errors on Camera open:** Ensure no other application (like Zoom or Teams) is using the webcam.
- **`ModuleNotFoundError: No module named 'pymongo'`:** You are mistakenly using the wrong Python version (e.g., Python 3.13) to run the scripts. The `start_system.bat` explicitly uses `py -3.11`.
- **Dashboard Data not changing:** Ensure MongoDB is actively running in the background (`mongod`). Open MongoDB Compass and confirm that the `eldercare_db` is populated.
