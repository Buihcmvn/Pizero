import io
import time
import requests
import threading
from flask import Flask, Response, send_file
from picamera2 import Picamera2
from gpiozero import MotionSensor, Button

app = Flask(__name__)

# --- CONFIGURATION ---
PIR_PIN = 17                    # PIR motion sensor connected to GPIO 17
BUTTON_PIN = 22                 # Doorbell button connected between GPIO 22 and GND

SERVER_BASE_URL = "http://192.168.0.27:8080"  # Replace with your Server IP address
SERVER_MOTION_URL = f"{SERVER_BASE_URL}/api/motion-alert"
SERVER_BELL_URL = f"{SERVER_BASE_URL}/api/doorbell-alert"

# Initialize hardware components using gpiozero
pir = MotionSensor(PIR_PIN)
button = Button(BUTTON_PIN, pull_up=True)

class CameraStream:
    def __init__(self):
        print("[*] Initializing Picamera2...")
        self.picam2 = Picamera2()
        config = self.picam2.create_video_configuration(
            main={"size": (640, 480), "format": "RGB888"},
            controls={"FrameDurationLimits": (33333, 66666)}
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(1)

    def capture_jpeg(self):
        buf = io.BytesIO()
        self.picam2.capture_file(buf, format='jpeg')
        buf.seek(0)
        return buf

    def generate_frames(self):
        while True:
            buf = self.capture_jpeg()
            frame = buf.getvalue()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

camera = None

def get_camera():
    global camera
    if camera is None:
        camera = CameraStream()
    return camera

# --- EVENT HANDLERS ---

def send_motion_alert():
    """Send lightweight motion alert webhook to the Server"""
    def _send():
        try:
            print("[!] Motion detected -> Sending motion alert to Server...")
            payload = {"event": "motion_detected", "device": "pizero_01", "timestamp": time.time()}
            requests.post(SERVER_MOTION_URL, json=payload, timeout=2)
        except Exception as e:
            print(f"[-] Error sending motion alert: {e}")

    threading.Thread(target=_send, daemon=True).start()

def send_doorbell_alert():
    """Send doorbell button press event webhook to the Server"""
    def _send():
        try:
            print("[!] Doorbell pressed -> Sending bell alert to Server...")
            payload = {"event": "doorbell_pressed", "device": "pizero_01", "timestamp": time.time()}
            requests.post(SERVER_BELL_URL, json=payload, timeout=2)
        except Exception as e:
            print(f"[-] Error sending doorbell alert: {e}")

    threading.Thread(target=_send, daemon=True).start()

# Bind hardware events
pir.when_motion = send_motion_alert
button.when_pressed = send_doorbell_alert

# --- FLASK ENDPOINTS FOR SERVER DATA RETRIEVAL ---

@app.route('/capture')
def capture():
    """API endpoint for the Server to fetch a single snapshot image"""
    cam = get_camera()
    buf = cam.capture_jpeg()
    return send_file(buf, mimetype='image/jpeg')

@app.route('/video_feed')
def video_feed():
    """Live MJPEG stream endpoint"""
    cam = get_camera()
    return Response(cam.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)