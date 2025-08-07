import paho.mqtt.client as mqtt
import json
import cv2
import os
import datetime
import threading
import time

# ---------------- MQTT Config ----------------
COMMAND_BROKER = "broker.emqx.io"
COMMAND_PORT = 1883
COMMAND_TOPIC = "/camera/manual"

RESULT_BROKER = "191.20.110.47"
RESULT_PORT = 1883
RESULT_TOPIC = "v1/devices/me/attributes"
RESULT_ACCESS_TOKEN = "camera_token"

# ---------------- Video Config ----------------
RTSP_URL = "rtsp://admin:%40mwte%40mp@55@192.168.0.87/Streaming/channels/101"
SAVE_PATH = "/home/brisk/netdrive/01-Organize/01-Management/01-Data Center/Brisk/06-AI & Machine Learning (D0340)/04-IOT_Smartfarm"
os.makedirs(SAVE_PATH, exist_ok=True)

# ---------------- Global ----------------
is_recording = False
cap = None
out = None
filename = None
video_path = None

# ---------------- MQTT Callbacks ----------------
def on_connect_command(client, userdata, flags, rc):
    if rc == 0:
        print(f"\n[COMMAND] Connected to MQTT Broker: {COMMAND_BROKER}")
        print(f"[COMAMND] Port: {COMMAND_PORT}")
        client.subscribe(COMMAND_TOPIC)
        print(f"[COMMAND] Subscribed to topic: {COMMAND_TOPIC}")
    else:
        print(f"[COMMAND] Failed to connect, rc={rc}")

def on_connect_result(client, userdata, flags, rc):
    if rc == 0:
        print(f"[RESULT] Connected to ThingsBoard Broker: {RESULT_BROKER}")
        print(f"[RESULT] Port: {RESULT_PORT}")
        print(f"[RESULT] Ready to publish to topic: {RESULT_TOPIC}")
    else:
        print(f"[RESULT] Failed to connect to ThingsBoard, rc={rc}")

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


# ---------------- Video Recording ----------------
def record_video():
    global cap, out, is_recording, filename, video_path

    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("Failed to connect to RTSP stream.")
        send_result({"video_status": "Failed to connect to RTSP."})
        return
    
    filename = f"video_smartfarm_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.mp4"
    video_path = os.path.join(SAVE_PATH, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 15.0, (640, 360))
    
    print(f"[COMMAND] Video recording started. {filename}")

    send_result({
    "video_status": "Recording in process ...",
    "filename": filename
    })

    start_time = time.time()
    time_recorded = 0  

    while is_recording:
        ret, frame = cap.read()
        if not ret:
            print("Frame not received.")
            break
        frame_resized = cv2.resize(frame, (640, 360))
        out.write(frame_resized)
        
        elapsed_time = int(time.time() - start_time)
        if elapsed_time != time_recorded:
            time_recorded = elapsed_time
            send_result({
            "elapsed_time": elapsed_time
            })

    cap.release()
    out.release()

    send_result({"video_status": "Recording completed."})
    print(f"[RESULT] Recording completed and file saved at {video_path}")
    
    filename = None
    video_path = None

# ---------------- Message Handler ----------------
def on_message_command(client, userdata, msg):
    global is_recording

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        if "camera" not in data:
            return 
        print(f"\n[COMMAND] Received: {data}")
    except Exception as e:
        print(f"[COMMAND] Invalid JSON: {e}")
        return


    if isinstance(data, dict) and "camera" in data:
        camera_state = data["camera"]

        if camera_state is True:
            if not is_recording:
                is_recording = True
                threading.Thread(target=record_video, daemon=True).start()
            else:
                print("Already recording.")
        elif camera_state is False:
            if is_recording:
                is_recording = False
            else:
                print("Already stopped.")
    else:
        print(f"[COMMAND] Unknown message format: {data}")

# ---------------- Start Clients ----------------
command_client = mqtt.Client()
command_client.on_connect = on_connect_command
command_client.on_message = on_message_command
command_client.connect(COMMAND_BROKER, COMMAND_PORT)

result_client = mqtt.Client()
result_client.username_pw_set(RESULT_ACCESS_TOKEN)
result_client.on_connect = on_connect_result
result_client.connect(RESULT_BROKER, RESULT_PORT)
result_client.loop_start()

command_client.loop_forever()

