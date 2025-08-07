import cv2
from flask import Flask, render_template, Response

app = Flask(__name__)

class VideoCamera:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.video = cv2.VideoCapture(rtsp_url)
        if not self.video.isOpened():
            print(f"Failed to connect to {rtsp_url}")
            raise Exception(f"Unable to connect to camera: {rtsp_url}")
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 2560)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 1440)

    def __del__(self):
        if self.video.isOpened():
            self.video.release()

    def get_frame(self):
        success, frame = self.video.read()
        if success:
            return frame
        else:
            print(f"Failed to capture frame from {self.rtsp_url}")
            return None

def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame is not None:
            success, buffer = cv2.imencode('.jpg', frame)
            if success:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n\r\n')
        else:
            print("No frame received from RTSP stream")
            break

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_cam1')
def video_feed_cam1():
    try:
        return Response(gen(VideoCamera("rtsp://191.20.207.53:8554/cam1")),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/video_cam2')
def video_feed_cam2():
    try:
        return Response(gen(VideoCamera("rtsp://191.20.207.53:8554/cam2")),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)