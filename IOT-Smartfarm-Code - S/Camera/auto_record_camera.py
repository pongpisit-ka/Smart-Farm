import cv2
import os
import datetime
import threading
import time
import json
import paho.mqtt.client as mqtt

# ---------------- Configuration ----------------
RTSP_URL = "rtsp://admin:%40mwte%40mp@55@192.168.0.88/Streaming/channels/101"
SAVE_PATH = "/home/brisk/netdrive/01-Organize/01-Management/01-Data Center/Brisk/06-AI & Machine Learning (D0340)/04-IOT_Smartfarm"
VIDEO_SIZE = (640, 360)
FPS = 25
RECORD_DURATION = 60
RECORD_INTERVAL = 3600

COMMAND_BROKER = "broker.emqx.io"
COMMAND_PORT = 1883
COMMAND_TOPIC = "/camera/manual"

RESULT_BROKER = "191.20.110.47"  
RESULT_PORT = 1883
RESULT_TOPIC = "v1/devices/me/attributes"
RESULT_ACCESS_TOKEN = "wmpXGE56uuCbYNor0tkl"

os.makedirs(SAVE_PATH, exist_ok=True)

# ---------------- Global State ----------------
is_schedule_running = False
last_command = None
filename = None
# ---------------- Video Recording Function ----------------
def record_video(duration):
    global filename

    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("Failed to connect to RTSP stream.")
        return

    filename = f"video_smartfarm_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.mp4"
    video_path = os.path.join(SAVE_PATH, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, FPS, VIDEO_SIZE)

    print(f"[COMMAND] Start recording: {filename}")
    send_result({"video_status_auto": "Recording in process ...",
                "filename_auto": filename})

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
    print(f"[COMMAND] Recording finished and file saved at: {video_path}")

# ---------------- Scheduled Loop Function ----------------
def schedule_recording():
    global is_schedule_running
    print("[COMMAND] Scheduled recording started.")
    while is_schedule_running:
        threading.Thread(target=record_video, args=(RECORD_DURATION,), daemon=True).start()
        time.sleep(RECORD_INTERVAL)
    print("[COMMAND] Scheduled recording stopped.")

# ---------------- MQTT Callbacks ----------------
def on_connect_command(client, userdata, flags, rc):
    if rc == 0:
        print(f"\n[COMMAND] Connected to MQTT Broker: {COMMAND_BROKER}")
        print(f"[COMMAND] Port: {COMMAND_PORT}")
        client.subscribe(COMMAND_TOPIC)
        print(f"[COMMAND] Subscribed to topic: {COMMAND_TOPIC}")
    else:
        print(f"[COMMAND] Failed to connect, rc={rc}")

def on_connect_result(client, userdata, flags, rc):
    if rc == 0:
        print(f"[RESULT] Connected to MQTT Broker: {RESULT_BROKER}")
        print(f"[RESULT] Port: {RESULT_PORT}")
        print(f"[RESULT] Ready to publish to topic: {RESULT_TOPIC}")
    else:
        print(f"[RESULT] Failed to connect, rc={rc}")

def on_message_command(client, userdata, msg):
    global is_schedule_running, last_command, filename

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        print(f"\n[COMMAND] Received message: {data}")

        
        state = data["camera"]

        if state == last_command:
            print("Already in process.")
            return
        last_command = state

        if state is True and not is_schedule_running:
            is_schedule_running = True
            threading.Thread(target=schedule_recording, daemon=True).start()

        elif state is False and is_schedule_running:
            is_schedule_running = False
            send_result({"video_status_auto": "Recording completed."})

        elif state is True and is_schedule_running:
            print("Already recording.")

        elif state is False and not is_schedule_running:
            print("Already stopped.")
        else:
            print("Unknown message format.")

    except Exception as e:
        print(f"Error handling command: {e}")

# ---------------- Send Result to ThingsBoard ----------------
def send_result(payload: dict):
    try:
        json_data = json.dumps(payload)
        result_client.publish(RESULT_TOPIC, json_data)
        print(f"\r[RESULT] Published: {json_data}", end="", flush=True)
    except Exception as e:
        print(f"[RESULT] Failed to publish: {e}")


# ---------------- Initialize MQTT Clients ----------------
command_client = mqtt.Client()
command_client.on_connect = on_connect_command
command_client.on_message = on_message_command
command_client.connect(COMMAND_BROKER, COMMAND_PORT)

result_client = mqtt.Client()
result_client.username_pw_set(RESULT_ACCESS_TOKEN)
result_client.on_connect = on_connect_result
result_client.connect(RESULT_BROKER, RESULT_PORT)
result_client.loop_start()

# ---------------- Listening MQTT Forever----------------
command_client.loop_forever()


