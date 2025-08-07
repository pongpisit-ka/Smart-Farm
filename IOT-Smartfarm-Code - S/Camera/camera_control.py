import cv2
import os
import datetime
import threading
import time
import json
import paho.mqtt.client as mqtt

# ---------------- Configuration ----------------
RTSP_URL = "rtsp://admin:%40mwte%40mp@55@192.168.0.88/Streaming/channels/101"
SAVE_PATH = r"R:\01-Organize\01-Management\01-Data Center\Brisk\06-AI & Machine Learning (D0340)\04-IOT_Smartfarm\video_smartfarm"
VIDEO_SIZE = (1920, 1080)
FPS = 25
RECORD_DURATION = 60
RECORD_INTERVAL = 3600

COMMAND_BROKER = "broker.emqx.io"
COMMAND_PORT = 1883
COMMAND_TOPIC = "/camera/manual"

RESULT_BROKER = "191.20.110.47"  
RESULT_PORT = 1883
RESULT_TOPIC = "v1/devices/me/attributes"
RESULT_ACCESS_TOKEN = "camera_token"

os.makedirs(SAVE_PATH, exist_ok=True)

# ---------------- Global State ----------------
is_schedule_running = False
is_recording = False
last_command_auto = None
last_command_manual = None
filename = None
video_path = None

# ---------------- Send Result to ThingsBoard ----------------
def send_result(payload: dict):
    try:
        json_data = json.dumps(payload)
        result_client.publish(RESULT_TOPIC, json_data)

        if "elapsed_time" in payload:
            print(f"\r[RESULT] Published: {json_data}", end="", flush=True)
        else:
            print(f"\n[RESULT] Published: {json_data}") 
    except Exception as e:
        print(f"\n[RESULT] Failed to publish: {e}")

# ---------------- Auto Recording ----------------
def record_video_auto(duration):
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("Failed to connect to RTSP stream.")
        send_result({"video_status": "Failed to connect to RTSP."})
        return

    filename = f"video_smartfarm_auto_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.mp4"
    video_path = os.path.join(SAVE_PATH, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, FPS, VIDEO_SIZE)

    print(f"[AUTO Mode] Start recording: {filename}")
    send_result({"video_status_auto": "Recording in process ...", "filename_auto": filename})

    start_time = time.time()

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            print("Frame not received.")
            break
        frame_resized = cv2.resize(frame, VIDEO_SIZE)
        out.write(frame_resized)

    cap.release()
    out.release()
    print(f"[AUTO Mode] Recording finished and file saved at: {video_path}")

    video_auto, _ = count_videos()
    send_result({
        "video_count_auto": video_auto
    })

# ---------------- Count Numer of Video ----------------
def count_videos():
    files = os.listdir(SAVE_PATH)
    auto_files = [f for f in files if f.startswith("video_smartfarm_auto") and f.endswith(".mp4")]
    manual_files = [f for f in files if f.startswith("video_smartfarm_manual") and f.endswith(".mp4")]
    return len(auto_files), len(manual_files)

# ---------------- Manual Recording ----------------
def record_video_manual():
    global cap, out, is_recording

    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("Failed to connect to RTSP stream.")
        send_result({"video_status": "Failed to connect to RTSP."})
        return

    filename = f"video_smartfarm_manual_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.mp4"
    video_path = os.path.join(SAVE_PATH, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 15.0, VIDEO_SIZE)

    print(f"[MANUAL Mode] Video recording started. {filename}")
    send_result({"video_status": "Recording in process ...", "filename": filename})

    start_time = time.time()
    time_recorded = 0

    while is_recording:
        ret, frame = cap.read()
        if not ret:
            print("Frame not received.")
            break
        frame_resized = cv2.resize(frame, VIDEO_SIZE)
        out.write(frame_resized)

        elapsed_time = int(time.time() - start_time)
        if elapsed_time != time_recorded:
            time_recorded = elapsed_time
            send_result({"elapsed_time": elapsed_time})

    cap.release()
    out.release()
    send_result({"video_status": "Recording completed."})
    print(f"[MANUAL Mode] Recording completed and file saved at {video_path}")

    _, video_manual = count_videos()
    send_result({
        "video_count_manual": video_manual
    })
# ---------------- Schedule Auto ----------------
def schedule_recording():
    global is_schedule_running
    print("[AUTO Mode] Scheduled recording started.")
    while is_schedule_running:
        threading.Thread(target=record_video_auto, args=(RECORD_DURATION,), daemon=True).start()
        time.sleep(RECORD_INTERVAL)
    print("[AUTO Mode] Scheduled recording stopped.")

# ---------------- MQTT Callbacks ----------------
def connect_command(client, userdata, flags, rc):
    if rc == 0:
        print(f"\n[COMMAND] Connected to MQTT Broker: {COMMAND_BROKER}")
        print(f"[COMMAND] Port: {COMMAND_PORT}")
        client.subscribe(COMMAND_TOPIC)
        print(f"[COMMAND] Subscribed to topic: {COMMAND_TOPIC}")
    else:
        print(f"[COMMAND] Failed to connect, rc={rc}")

def connect_result(client, userdata, flags, rc):
    if rc == 0:
        print(f"[RESULT] Connected to ThingsBoard Broker: {RESULT_BROKER}")
        print(f"[RESULT] Port: {RESULT_PORT}")
        print(f"[RESULT] Ready to publish to topic: {RESULT_TOPIC}")
    else:
        print(f"[RESULT] Failed to connect to ThingsBoard, rc={rc}")

def message_command(client, userdata, msg):
    global is_schedule_running, last_command_auto, last_command_manual, is_recording

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        if "camera_auto" not in data and "camera_manual" not in data:
            return

        print(f"\n[COMMAND] Received: {data}")
    except Exception as e:
        print(f"[COMMAND] Invalid JSON: {e}")
        return

    # ----- AUTO Mode -----
    if "camera_auto" in data:
        state = data["camera_auto"]
        if state == last_command_auto:
            print("[AUTO Mode] Already in process.")
            return
        last_command_auto = state

        if state is True:
            if is_recording:
                print("[AUTO Mode] Cannot start. Manual Mode recording is in progress.")
                send_result({"video_status_auto": "Cannot start. Manual Mode recording in progress."})
                return
            if not is_schedule_running:
                is_schedule_running = True
                threading.Thread(target=schedule_recording, daemon=True).start()
            else:
                print("[AUTO Mode] Already recording.")
        elif state is False:
            if is_schedule_running:
                is_schedule_running = False
                send_result({"video_status_auto": "Recording completed."})
            else:
                print("[AUTO Mode] Already stopped.")

    # ----- MANUAL Mode -----
    elif "camera_manual" in data:
        state = data["camera_manual"]
        if state == last_command_manual:
            print("[MANUAL Mode] Already in process.")
            return
        last_command_manual = state

        if state is True:
            if is_schedule_running:
                print("[MANUAL Mode] Cannot start. Auto Mode recording is in progress.")
                send_result({"video_status": "Cannot start. Auto Mode recording in progress."})
                return
            if not is_recording:
                is_recording = True
                threading.Thread(target=record_video_manual, daemon=True).start()
            else:
                print("[MANUAL Mode] Already recording.")
        elif state is False:
            if is_recording:
                is_recording = False
            else:
                print("[MANUAL Mode] Already stopped.")


# ---------------- Initialize MQTT Clients ----------------
command_client = mqtt.Client()
command_client.on_connect = connect_command
command_client.on_message = message_command
command_client.connect(COMMAND_BROKER, COMMAND_PORT)

result_client = mqtt.Client()
result_client.username_pw_set(RESULT_ACCESS_TOKEN)
result_client.on_connect = connect_result
result_client.connect(RESULT_BROKER, RESULT_PORT)
result_client.loop_start()

command_client.loop_forever()