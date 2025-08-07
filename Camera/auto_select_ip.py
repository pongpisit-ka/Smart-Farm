import subprocess
import cv2

camera_links = [
    "rtsp://admin:%40mwte%40mp@55@192.168.0.86/Streaming/channels/101",
    "rtsp://admin:%40mwte%40mp@55@192.168.0.87/Streaming/channels/101",
    "rtsp://admin:%40mwte%40mp@55@192.168.0.88/Streaming/channels/101",
    "rtsp://admin:%40mwte%40mp@55@192.168.0.89/Streaming/channels/101",
]

def is_rtsp_working(link):
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-timeout", "1000000",          
                "-rtsp_transport", "tcp",
                "-i", link,
                "-t", "1",                     
                "-f", "null", "-"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False

def find_first_working_camera(links):
    for i, link in enumerate(links):
        print(f"🔍 Checking camera {i+1}")
        if is_rtsp_working(link):
            print(f"✅ Found working camera: {link}")
            return link
        else:
            print(f"❌ Camera {i+1} not accessible.")
    return None

# 🔎 ตรวจลิงก์
rtsp_url = find_first_working_camera(camera_links)

# 🎥 แสดงกล้อง
if rtsp_url:
    cap = cv2.VideoCapture(rtsp_url)
    if cap.isOpened():
        print(f"📷 Showing stream from: {rtsp_url}")
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to read frame.")
                break
            frame_resized = cv2.resize(frame, (1080, 720))
            cv2.imshow("RTSP Stream", frame_resized)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()
    else:
        print("❌ Failed to open RTSP stream.")
else:
    print("🚫 No accessible RTSP camera found.")
