import os
import time
import requests
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
PI_ZERO_IP = "192.168.0.23"  # Replace with the actual IP address of the Pi Zero W
PI_CAPTURE_URL = f"http://{PI_ZERO_IP}:5000/capture"
SAVE_DIR = "./captured_images"

os.makedirs(SAVE_DIR, exist_ok=True)

# Manage the image pulling timer on the server side
last_motion_time = 0
is_pulling = False
pull_lock = threading.Lock()

def pull_images_from_pi():
    """Server-side thread: Continuously fetch images from the Pi Zero's IP"""
    global is_pulling, last_motion_time
    print("[SERVER] Started pulling images from Pi Zero W...")

    PULL_DURATION = 20  # Server continues pulling images for 20 seconds after the last trigger
    PULL_INTERVAL = 1.0 # Fetch 1 image every second

    while True:
        try:
            # Server actively downloads the image from the Pi
            res = requests.get(PI_CAPTURE_URL, timeout=3)
            if res.status_code == 200:
                filename = f"{SAVE_DIR}/motion_{int(time.time())}.jpg"
                with open(filename, 'wb') as f:
                    f.write(res.content)
                print(f"[SERVER] Saved image: {filename}")
        except Exception as e:
            print(f"[SERVER] Error pulling image from Pi: {e}")

        time.sleep(PULL_INTERVAL)

        # Check if PULL_DURATION has elapsed since the last motion alert
        if time.time() - last_motion_time >= PULL_DURATION:
            print("[SERVER] Duration timeout reached. Stopping image pull.")
            with pull_lock:
                is_pulling = False
            break

@app.route('/api/motion-alert', methods=['POST'])
def motion_alert():
    """Endpoint receiving motion detection webhook from Pi Zero"""
    global last_motion_time, is_pulling
    data = request.json
    print(f"[SERVER] Received motion alert from {data.get('device')}: Motion detected!")
    
    last_motion_time = time.time()

    with pull_lock:
        if not is_pulling:
            is_pulling = True
            threading.Thread(target=pull_images_from_pi, daemon=True).start()

    return jsonify({"status": "received"}), 200

@app.route('/api/doorbell-alert', methods=['POST'])
def doorbell_alert():
    """Endpoint receiving doorbell button press webhook from Pi Zero"""
    data = request.json
    print(f"[SERVER] 🔔 DOORBELL PRESSED from {data.get('device')} at timestamp {data.get('timestamp')}!")
    
    # You can add custom handling here, such as:
    # - Triggering an audio sound alert on the server speaker
    # - Sending a push notification (Telegram, FCM, etc.) to your phone
    # - Forcing an immediate image capture snapshot
    try:
        res = requests.get(PI_CAPTURE_URL, timeout=3)
        if res.status_code == 200:
            filename = f"{SAVE_DIR}/doorbell_{int(time.time())}.jpg"
            with open(filename, 'wb') as f:
                f.write(res.content)
            print(f"[SERVER] Saved doorbell snapshot: {filename}")
    except Exception as e:
        print(f"[SERVER] Error capturing doorbell image: {e}")

    return jsonify({"status": "bell_acknowledged"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)