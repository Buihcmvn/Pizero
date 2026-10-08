#!/usr/bin/env python3
"""
Raspberry Pi Zero W Camera Streaming Server (Backend)
Handles camera frame capture and serves the Flask routes.
"""

import io
import time
from flask import Flask, Response, render_template

# Try importing picamera2 (standard for Raspberry Pi OS Bullseye/Bookworm), 
# fall back to picamera for older OS versions, or OpenCV if neither is available.
CAMERA_TYPE = None
try:
    from picamera2 import Picamera2
    CAMERA_TYPE = "picamera2"
except ImportError:
    try:
        import picamera
        CAMERA_TYPE = "picamera"
    except ImportError:
        import cv2
        CAMERA_TYPE = "opencv"

app = Flask(__name__, template_folder='templates')

class CameraStream:
    def __init__(self):
        self.type = CAMERA_TYPE
        print(f"[*] Initializing camera using driver: {self.type}")
        
        if self.type == "picamera2":
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(main={"size": (640, 480)})
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(1) # Camera warm-up
        elif self.type == "picamera":
            self.camera = picamera.PiCamera()
            self.camera.resolution = (640, 480)
            self.camera.framerate = 15
            time.sleep(1)
        elif self.type == "opencv":
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def get_frame(self):
        """Capture frame and return as JPEG bytes."""
        if self.type == "picamera2":
            stream = io.BytesIO()
            self.picam2.capture_file(stream, format='jpeg')
            return stream.getvalue()
            
        elif self.type == "picamera":
            stream = io.BytesIO()
            self.camera.capture(stream, format='jpeg', use_video_port=True)
            return stream.getvalue()
            
        elif self.type == "opencv":
            success, frame = self.cap.read()
            if not success:
                return None
            _, jpeg = cv2.imencode('.jpg', frame)
            return jpeg.tobytes()

        return None

# Global camera instance
camera = CameraStream()

def generate_frames():
    """Generator function that continuously yields JPEG frames."""
    while True:
        frame_bytes = camera.get_frame()
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.05)  # Limit frame rate (~20 FPS) to save Pi Zero CPU

@app.route('/')
def index():
    """Render the web UI for client browsers from templates/index.html."""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route for MJPEG stream."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Run server accessible from any device on port 5000
    app.run(host='0.0.0.0', port=5000, threaded=True)