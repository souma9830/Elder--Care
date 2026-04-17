
import cv2
import mediapipe as mp
import numpy as np
import threading
import time
import math
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
FALL_CONFIRM_FRAMES   = 25       # Consecutive frames needed to confirm a fall
FALL_COOLDOWN_SECONDS = 5        # Min seconds between TTS announcements
TORSO_ANGLE_THRESHOLD = 45       # Degrees — below this = likely fallen
SHOULDER_ANKLE_RATIO  = 0.25     # Shoulder Y near ankle Y = fallen
BBOX_RATIO_THRESHOLD  = 1.1      # width/height > this = horizontal (fallen)
MIN_POSE_CONFIDENCE   = 0.55     # Minimum landmark visibility to trust result

# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS CONFIG  ← Fill in your own credentials here
# ─────────────────────────────────────────────────────────────────────────────

# ── Gmail ───────────────────────────────────────────────────────────────────────
GMAIL_ENABLED      = False                  # Set True and fill in your real credentials to enable
GMAIL_SENDER       = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"  # 16-char App Password from myaccount.google.com
GMAIL_RECIPIENTS   = ["recipient@example.com"]
GMAIL_SUBJECT      = "⚠️ FALL DETECTED – Immediate Attention Required"
GMAIL_COOLDOWN_SEC = 60

# ─────────────────────────────────────────────────────────────────────────────
# GMAIL NOTIFIER
# ─────────────────────────────────────────────────────────────────────────────
class GmailNotifier:
    """Sends an HTML e-mail via Gmail SMTP in a background thread."""

    def __init__(self):
        self._last_sent = 0
        self._lock = threading.Lock()

    def _build_message(self, timestamp: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = GMAIL_SUBJECT
        msg["From"]    = GMAIL_SENDER
        msg["To"]      = ", ".join(GMAIL_RECIPIENTS)

        plain = (
            f"FALL DETECTED!\n\n"
            f"Time: {timestamp}\n\n"
            f"The fall detection system has identified a potential fall event.\n"
            f"Please check on the monitored individual immediately.\n\n"
            f"-- Fall Detection System"
        )

        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
          <div style="max-width:520px;margin:auto;background:#fff;border-radius:10px;
                      box-shadow:0 2px 8px rgba(0,0,0,0.15);overflow:hidden;">
            <div style="background:#c0392b;padding:24px;text-align:center;">
              <h1 style="color:#fff;margin:0;font-size:26px;">⚠️ FALL DETECTED</h1>
            </div>
            <div style="padding:28px;">
              <p style="font-size:16px;color:#333;">
                The <strong>Fall Detection System</strong> has identified a potential fall event.
              </p>
              <table style="width:100%;border-collapse:collapse;margin:16px 0;">
                <tr>
                  <td style="padding:10px;background:#fdecea;border-radius:6px;
                             font-size:15px;color:#777;">🕐 Detection Time</td>
                  <td style="padding:10px;background:#fdecea;border-radius:6px;
                             font-size:15px;font-weight:bold;color:#333;">{timestamp}</td>
                </tr>
              </table>
              <p style="font-size:15px;color:#555;">
                Please <strong>check on the monitored individual immediately</strong>
                and call for medical assistance if necessary.
              </p>
              <div style="margin-top:24px;padding:14px;background:#fff3f3;
                          border-left:4px solid #c0392b;border-radius:4px;">
                <p style="margin:0;color:#c0392b;font-size:14px;">
                  This is an automated alert from your Fall Detection System.
                </p>
              </div>
            </div>
          </div>
        </body></html>
        """

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))
        return msg

    def _send(self, timestamp: str):
        try:
            msg = self._build_message(timestamp)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_SENDER, GMAIL_RECIPIENTS, msg.as_string())
            print(f"[GMAIL] ✅ Alert sent at {timestamp}")
        except smtplib.SMTPAuthenticationError:
            print("[GMAIL] ❌ Auth failed — check GMAIL_APP_PASSWORD (use an App Password, not your login password).")
        except Exception as e:
            print(f"[GMAIL] ❌ Failed to send: {e}")

    def notify(self):
        """Fire-and-forget notification with cooldown protection."""
        if not GMAIL_ENABLED:
            return
        now = time.time()
        with self._lock:
            if now - self._last_sent < GMAIL_COOLDOWN_SEC:
                return
            self._last_sent = now

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        t = threading.Thread(target=self._send, args=(timestamp,), daemon=True)
        t.start()





# ─────────────────────────────────────────────────────────────────────────────
# TTS ANNOUNCER (runs in background thread so it doesn't block video)
# ─────────────────────────────────────────────────────────────────────────────
class Announcer:
    def __init__(self):
        self._last_announced = 0
        self._lock = threading.Lock()

    def announce(self, message: str):
        """Speak message in a background thread with cooldown protection."""
        now = time.time()
        with self._lock:
            if now - self._last_announced < FALL_COOLDOWN_SECONDS:
                return
            self._last_announced = now

        def _speak():
            try:
                import pyttsx3
                import pythoncom
                pythoncom.CoInitialize() # Required for COM in background thread
                engine = pyttsx3.init()
                engine.setProperty('rate', 145)
                engine.setProperty('volume', 1.0)
                engine.say(message)
                engine.runAndWait()
            except Exception as e:
                print(f"[TTS ALERT] {e}")

        t = threading.Thread(target=_speak, daemon=True)
        t.start()


# ─────────────────────────────────────────────────────────────────────────────
# FALL DETECTION LOGIC
# ─────────────────────────────────────────────────────────────────────────────
class FallDetector:
    def __init__(self):
        self._fall_frame_count = 0
        self._fall_confirmed = False

    def _get_landmark(self, landmarks, idx, frame_h, frame_w):
        """Returns (x_px, y_px, visibility) for a landmark."""
        lm = landmarks[idx]
        return (int(lm.x * frame_w), int(lm.y * frame_h), lm.visibility)

    def _midpoint(self, p1, p2):
        """Pixel midpoint between two (x,y,vis) points."""
        return ((p1[0]+p2[0])//2, (p1[1]+p2[1])//2)

    def _angle_with_vertical(self, top, bottom):
        """
        Angle (degrees) between the line [top→bottom] and the vertical axis.
        0° = perfectly vertical (standing), 90° = perfectly horizontal (fallen).
        """
        dx = bottom[0] - top[0]
        dy = bottom[1] - top[1]
        if dy == 0 and dx == 0:
            return 0
        angle_rad = math.atan2(abs(dx), abs(dy))  # angle from vertical
        return math.degrees(angle_rad)

    def analyze(self, landmarks, frame_h, frame_w):
        """
        Runs the 3-factor fall analysis and returns:
          (is_fall: bool, confidence: float 0–1, debug_info: dict)
        """
        # Core landmarks
        L_SHOULDER, R_SHOULDER = 11, 12
        L_HIP,      R_HIP      = 23, 24
        L_ANKLE,    R_ANKLE    = 27, 28
        L_KNEE,     R_KNEE     = 25, 26
        NOSE                   = 0

        lm = landmarks

        # Gather points
        ls = self._get_landmark(lm, L_SHOULDER, frame_h, frame_w)
        rs = self._get_landmark(lm, R_SHOULDER, frame_h, frame_w)
        lh = self._get_landmark(lm, L_HIP,      frame_h, frame_w)
        rh = self._get_landmark(lm, R_HIP,      frame_h, frame_w)
        la = self._get_landmark(lm, L_ANKLE,    frame_h, frame_w)
        ra = self._get_landmark(lm, R_ANKLE,    frame_h, frame_w)

        # Check sufficient visibility
        key_vis = [ls[2], rs[2], lh[2], rh[2]]
        avg_vis = sum(key_vis) / len(key_vis)
        if avg_vis < MIN_POSE_CONFIDENCE:
            return False, 0.0, {"reason": "low visibility"}

        shoulder_mid = self._midpoint(ls, rs)
        hip_mid      = self._midpoint(lh, rh)
        ankle_mid    = self._midpoint(la, ra)

        # ── Factor 1: Torso angle ────────────────────────────────────────────
        torso_angle = self._angle_with_vertical(shoulder_mid, hip_mid)
        # 0 = vertical (standing), 90 = horizontal (fallen)
        factor1_score = min(torso_angle / 90.0, 1.0)

        # ── Factor 2: Shoulder height vs ankle height ────────────────────────
        # In image coords, Y increases downward.
        # Ankle Y should be LARGER than shoulder Y (ankles lower on screen).
        ankle_y  = ankle_mid[1]
        shoulder_y = shoulder_mid[1]
        if ankle_y > 0:
            # How close is shoulder_y to ankle_y, normalized
            factor2_score = 1.0 - min(abs(ankle_y - shoulder_y) / (frame_h + 1e-6), 1.0)
        else:
            factor2_score = 0.0

        # ── Factor 3: Bounding box aspect ratio ──────────────────────────────
        all_vis_pts = []
        for lmk in lm:
            if lmk.visibility > MIN_POSE_CONFIDENCE:
                all_vis_pts.append((int(lmk.x * frame_w), int(lmk.y * frame_h)))

        if all_vis_pts:
            xs = [p[0] for p in all_vis_pts]
            ys = [p[1] for p in all_vis_pts]
            bbox_w = max(xs) - min(xs) + 1
            bbox_h = max(ys) - min(ys) + 1
            ratio = bbox_w / bbox_h   # >1 means wider than tall
            # Map ratio to 0–1 score: ratio=1 → 0.0, ratio=2 → 1.0
            factor3_score = max(0.0, min((ratio - 1.0) / 1.0, 1.0))
        else:
            factor3_score = 0.0

        # ── Combined confidence (weighted) ────────────────────────────────────
        confidence = (
            0.45 * factor1_score +   # torso angle is most reliable
            0.30 * factor2_score +   # shoulder near ankle
            0.25 * factor3_score     # wide bounding box
        )

        is_fall = confidence > 0.50

        debug = {
            "torso_angle":   round(torso_angle, 1),
            "factor1":       round(factor1_score, 2),
            "factor2":       round(factor2_score, 2),
            "factor3":       round(factor3_score, 2),
            "confidence":    round(confidence, 2),
        }
        return is_fall, confidence, debug

    def update(self, is_fall_this_frame):
        """Accumulate frames and return confirmed fall state."""
        if is_fall_this_frame:
            self._fall_frame_count = min(self._fall_frame_count + 1, FALL_CONFIRM_FRAMES + 10)
        else:
            self._fall_frame_count = max(self._fall_frame_count - 2, 0)  # decay slowly

        self._fall_confirmed = self._fall_frame_count >= FALL_CONFIRM_FRAMES
        return self._fall_confirmed


# ─────────────────────────────────────────────────────────────────────────────
# UI DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────
class UI:
    # Colour palette
    GREEN       = (80, 200, 80)
    RED         = (60, 60, 220)     # BGR
    ORANGE      = (30, 165, 255)
    WHITE       = (255, 255, 255)
    BLACK       = (0, 0, 0)
    DARK_GREY   = (30, 30, 30)
    CYAN        = (220, 200, 50)

    @staticmethod
    def draw_status_badge(frame, is_fall, confidence):
        h, w = frame.shape[:2]
        label   = "FALL DETECTED!" if is_fall else "NORMAL"
        color   = UI.RED if is_fall else UI.GREEN
        bg_alpha = 0.75

        # Semi-transparent background badge
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (340, 70), UI.DARK_GREY, -1)
        cv2.addWeighted(overlay, bg_alpha, frame, 1 - bg_alpha, 0, frame)

        # Status text
        cv2.putText(frame, label, (20, 52),
                    cv2.FONT_HERSHEY_DUPLEX, 1.3, color, 2, cv2.LINE_AA)

        # Confidence bar
        bar_x, bar_y, bar_w, bar_h = 10, 75, 340, 18
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h), UI.DARK_GREY, -1)
        fill = int(bar_w * confidence)
        bar_color = UI.RED if confidence > 0.5 else UI.GREEN
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x+fill, bar_y+bar_h), bar_color, -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h), UI.WHITE, 1)
        cv2.putText(frame, f"Fall Confidence: {int(confidence*100)}%",
                    (bar_x+5, bar_y+13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, UI.WHITE, 1, cv2.LINE_AA)

    @staticmethod
    def draw_debug_panel(frame, debug, fps):
        h, w = frame.shape[:2]
        lines = [
            f"FPS: {fps:.1f}",
            f"Torso angle: {debug.get('torso_angle', '?')}°",
            f"Angle score:  {debug.get('factor1', '?')}",
            f"Height score: {debug.get('factor2', '?')}",
            f"BBox score:   {debug.get('factor3', '?')}",
        ]
        panel_h = len(lines) * 22 + 14
        overlay = frame.copy()
        cv2.rectangle(overlay, (w-200, h-panel_h-10), (w-10, h-10), UI.DARK_GREY, -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        for i, line in enumerate(lines):
            y = h - panel_h + i * 22 + 20
            cv2.putText(frame, line, (w-192, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, UI.CYAN, 1, cv2.LINE_AA)

    @staticmethod
    def draw_notification_status(frame, gmail_on: bool, telegram_on: bool):
        """Small indicator in top-right corner showing notification channels."""
        h, w = frame.shape[:2]
        icons = []
        if gmail_on:
            icons.append(("Gmail", UI.GREEN))
        if telegram_on:
            icons.append(("Telegram", UI.GREEN))

        overlay = frame.copy()
        panel_w, panel_h = 160, len(icons) * 22 + 10
        cv2.rectangle(overlay, (w - panel_w - 10, 8), (w - 10, panel_h + 8), UI.DARK_GREY, -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        for i, (label, color) in enumerate(icons):
            cv2.putText(frame, f"● {label}", (w - panel_w - 2, 26 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, color, 1, cv2.LINE_AA)

    @staticmethod
    def draw_flash(frame, is_fall):
        """Red border flash when fall is detected."""
        if is_fall:
            h, w = frame.shape[:2]
            for thickness, alpha in [(12, 0.6), (6, 0.9)]:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), UI.RED, thickness)
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("     Fall Detection System  - Starting")
    print("  Press  Q  to quit")
    print("=" * 50)
    print(f"  Gmail alerts   : {'ENABLED' if GMAIL_ENABLED else 'disabled'}")
    print("=" * 50)

    # MediaPipe setup
    mp_pose    = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_styles  = mp.solutions.drawing_styles

    pose = mp_pose.Pose(
        model_complexity=1,
        enable_segmentation=False,
        smooth_landmarks=True,
        min_detection_confidence=0.55,
        min_tracking_confidence=0.55,
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam. Check if it's connected.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Warm up the camera — discard first few frames
    for _ in range(5):
        cap.read()
    time.sleep(0.3)

    announcer      = Announcer()
    detector       = FallDetector()
    gmail_notifier = GmailNotifier()
    ui             = UI()

    # FPS calculation
    prev_time = time.time()
    fps = 0.0
    debug_info = {}
    last_post_time = 0  # throttle backend POST requests

    print("[INFO] Webcam opened. Monitoring for falls...")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Failed to grab frame, retrying...")
            time.sleep(0.05)
            continue

        frame = cv2.flip(frame, 1)   # mirror for natural feel
        h, w = frame.shape[:2]

        # ── Pose detection ───────────────────────────────────────────────────
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = pose.process(rgb)
        rgb.flags.writeable = True

        is_fall_raw  = False
        confidence   = 0.0

        if results.pose_landmarks:
            # Draw skeleton
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(
                    color=(255, 200, 50), thickness=2, circle_radius=3),
                connection_drawing_spec=mp_drawing.DrawingSpec(
                    color=(100, 220, 255), thickness=2),
            )

            is_fall_raw, confidence, debug_info = detector.analyze(
                results.pose_landmarks.landmark, h, w
            )

        # ── Confirmation & alerts ─────────────────────────────────────────────
        fall_confirmed = detector.update(is_fall_raw)

        if fall_confirmed:
            gmail_notifier.notify()   # sends e-mail (respects its own cooldown; disabled by default)

        # POST state to backend (throttled to every 2s, or immediately on fall)
        now_post = time.time()
        if fall_confirmed or (now_post - last_post_time) >= 2.0:
            last_post_time = now_post
            _payload = {"is_fall": bool(fall_confirmed), "confidence": float(confidence), "fps": float(fps)}
            if not debug_info:
                _payload["torso_angle"] = 0.0
            else:
                _payload.update(debug_info)
            
            def _send(p=_payload):
                try:
                    requests.post("http://127.0.0.1:5000/api/fall", json=p, timeout=2.0)
                except Exception:
                    pass
            threading.Thread(target=_send, daemon=True).start()

        # ── Draw UI ───────────────────────────────────────────────────────────
        UI.draw_flash(frame, fall_confirmed)
        UI.draw_status_badge(frame, fall_confirmed, confidence)
        UI.draw_notification_status(frame, GMAIL_ENABLED, False)
        if debug_info:
            UI.draw_debug_panel(frame, debug_info, fps)

        # ── FPS ───────────────────────────────────────────────────────────────
        now = time.time()
        fps = 1.0 / (now - prev_time + 1e-6)
        prev_time = now

        # ── Show frame ───────────────────────────────────────────────────────
        cv2.imshow("Fall Detection System", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    pose.close()
    print("[INFO] Stopped.")


if __name__ == "__main__":
    main()
