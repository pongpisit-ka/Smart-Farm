import subprocess
import os
import datetime
import threading
import time
import json
import paho.mqtt.client as mqtt
import signal
import platform
import re

# ---------------- Configuration ----------------
SAVE_PATH = r"R:\\01-Organize\\01-Management\\01-Data Center\\Brisk\\06-AI & Machine Learning (D0340)\\04-IOT_Smartfarm\\video_smartfarm"
VIDEO_SIZE = (1920, 1080)
FPS = 25
RECORD_DURATION = 60 # Auto mode duration in seconds
RECORD_INTERVAL = 1800 # Interval between auto recordings in seconds
LIMIT_TIME_MANUAL = 300  # Manual mode limited in seconds

COMMAND_BROKER = "broker.emqx.io" # Thingsboard send command to Python 
COMMAND_PORT = 1883
COMMAND_TOPIC = "/camera/manual"

RESULT_BROKER = "191.20.110.47"  # Python send result to ThingsBoard 
RESULT_PORT = 1883
RESULT_TOPIC = "v1/devices/me/attributes"
RESULT_ACCESS_TOKEN = "camera_token"

os.makedirs(SAVE_PATH, exist_ok=True)

# ---------------- Global State ----------------
# จัดการสถานะของกล้อง สถานะการบันทึก สถานะการตั้งเวลา และสถานะการควบคุมคำสั่งผ่านตัวแปร
class CameraState:
    def __init__(self):
        self.cameras = {
            "_0": {"is_schedule_running": False, "is_recording": False, 
                   "last_command_auto": None, "last_command_manual": None,
                   "ffmpeg_process": None, "stop_event": None, "is_waiting": False},
            "_1": {"is_schedule_running": False, "is_recording": False, 
                   "last_command_auto": None, "last_command_manual": None,
                   "ffmpeg_process": None, "stop_event": None,
                   "elapsed_time": {"auto": None, "manual": None}, "is_waiting": False},
            "_2": {"is_schedule_running": False, "is_recording": False, 
                   "last_command_auto": None, "last_command_manual": None,
                   "ffmpeg_process": None, "stop_event": None,
                   "elapsed_time": {"auto": None, "manual": None}, "is_waiting": False}
        }
        self.print_lock = threading.Lock()
        self.last_display_line = ""
        self.camera_ips = {}  
        self.camera_urls = {}  

camera_state = CameraState()

# ---------------- Logging Helper ----------------
# แสดงข้อความพร้อม timestamp โดยเคลียร์บรรทัดก่อนหน้าและคืนค่าบรรทัดล่าสุดจาก camera_state.last_display_line
def print_log(msg: str):
    print("\r" + " " * 120, end="\r")    
    print(f"| {datetime.datetime.now().strftime('%H:%M:%S')} | {msg}")

    if camera_state.last_display_line:
        print(f"\033[2K\r{camera_state.last_display_line}", end='', flush=True)

# ---------------- Camera Identification ----------------
# ดึง IP address จาก RTSP URL โดยตรวจสอบรูปแบบต่าง ๆ และใช้การแยกข้อความเพื่อค้นหา IP address
def extract_ip_from_rtsp(rtsp_url):
    if not rtsp_url or not isinstance(rtsp_url, str):
        return None

    # Medthod 1: Regular expression 
    ip_pattern = r'rtsp://[^:@/]*(?::[^@/]*)?@?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)'
    match = re.search(ip_pattern, rtsp_url)
    if match:
        return match.group(1)
    
    # Method 2: String Splitting
    try:
        url_without_protocol = rtsp_url.replace("rtsp://", "")
        if '@' in url_without_protocol:
            _, host_part = url_without_protocol.split('@', 1)
        else:
            host_part = url_without_protocol
        
        if '/' in host_part:
            host_part = host_part.split('/', 1)[0]

        if ':' in host_part:
            host_part = host_part.split(':', 1)[0]

        ip_parts = host_part.split('.')
        if len(ip_parts) == 4 and all(part.isdigit() for part in ip_parts):
            return host_part
    except Exception as e:
        print_log(f"[ERROR] Error extracting IP (method 2): {e}")

    # Method 3: Find something looklike IP Adress 
    ip_only_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    match = re.search(ip_only_pattern, rtsp_url)
    if match:
        return match.group(1)
    
    return None

# ---------------- Camera Identification ----------------
# กำหนด suffix ของกล้องจาก URL RTSP โดยตรวจสอบ IP address 
def get_suffix_from_rtsp(rtsp_url):
    # ตรวจสอบว่า rtsp_url เป็น str ไหม
    if not rtsp_url or not isinstance(rtsp_url, str):
        print_log(f"[WARNING] Invalid RTSP URL: {rtsp_url}")
        return "_0"
    
    # ตรวจสอบว่ามี rtsp_url ที่ camera_state.camera_urls หรือยัง
    if rtsp_url in camera_state.camera_urls:
        return camera_state.camera_urls[rtsp_url]

    # ดึง ip_address จาก rtsp_url ด้วยฟังก์ชัน extract_ip_from_rtsp
    ip_address = extract_ip_from_rtsp(rtsp_url)
    
    if ip_address:
        print_log(f"[INFO] Extracted IP from RTSP URL: {ip_address}")

        # ตรวจสอบว่ามี ip_address ใน camera_state.camera_ips ถ้ามีให้เก็บเป็นตัวแปรชื่อ suffix
        if ip_address in camera_state.camera_ips:
            suffix = camera_state.camera_ips[ip_address]
            camera_state.camera_urls[rtsp_url] = suffix
            print_log(f"[INFO] Using existing camera {suffix} for IP: {ip_address}")
            return suffix
        
        # กรณีไม่เคยเจอ IP Address มาก่อน จะกำหนด Suffix ให้กับ IP Address ใหม่
        camera_count = len(camera_state.camera_ips)
        if camera_count < 2: 
            new_suffix = f"_{camera_count + 1}"
            camera_state.camera_ips[ip_address] = new_suffix
            camera_state.camera_urls[rtsp_url] = new_suffix
            print_log(f"[INFO] Assigned NEW camera {new_suffix} to IP: {ip_address}")
            return new_suffix
    else:
        print_log(f"[WARNING] Could not extract IP from RTSP URL: {rtsp_url}")

    # กรณีไม่เคยเจอ IP Address มาก่อน จะกำหนด Suffix ให้กับ IP Address ใหม่
    camera_count = len(camera_state.camera_urls)
    if camera_count < 2:
        new_suffix = f"_{camera_count + 1}"
        camera_state.camera_urls[rtsp_url] = new_suffix
        print_log(f"[INFO] Assigned camera {new_suffix} to URL without IP")
        return new_suffix

    # กรณีจะเพิ่มกล้องตัวที่ 3 เข้ามา จะปฏิเสธและใช้ Suffix = _1 เป็นค่าเริ่มต้นเพื่อป้องกันข้อผิดพลาด
    print_log(f"[WARNING] Maximum cameras reached, using camera _1 for: {rtsp_url}")
    camera_state.camera_urls[rtsp_url] = "_1"
    return "_1"

# ---------------- Send Result to ThingsBoard ----------------
# ส่งข้อมูลผลลัพธ์ไปยัง MQTT Broker ผ่าน topic ที่กำหนดไว้และอัปเดตสถานะของกล้องในระบบ
def send_result(payload: dict, mode: str = "manual", suffix: str = "_0"):
    try:
        # แปลง payload ที่ได้รับ มาใส่ mode และ suffix เพื่อแยกแยะได้ว่าเป็นข้อมูลของกล้องตัวไหน เช่น {"elapsed_time": 10.5} เป็น elapsed_time_manual_1
        updated_payload = {f"{k}_{mode}{suffix}": v for k, v in payload.items()}
        json_data = json.dumps(updated_payload)
        result_client.publish(RESULT_TOPIC, json_data)

        # ถ้ามี elapsed_time ใน updated_payload ให้บันทึกค่า elapsed_time ใน camera_state.cameras[suffix] ตาม mode ที่กำหนด
        if any("elapsed_time" in k for k in updated_payload.keys()) and suffix in ["_1", "_2"]:
            if "elapsed_time" in payload:
                camera_state.cameras[suffix]["elapsed_time"][mode] = payload["elapsed_time"]

            # แสดงเวลาของกล้องในแต่ละโหมด (auto หรือ manual) และใช้ print_lock เพื่อป้องกันการพิมพ์ชนกันระหว่าง thread
            with camera_state.print_lock:
                status_line = ""
                for cam_suffix in ["_1", "_2"]:
                    for cam_mode in ["auto", "manual"]:
                        if cam_mode == "auto" and camera_state.cameras[cam_suffix]["is_schedule_running"]:
                            time_value = camera_state.cameras[cam_suffix]["elapsed_time"][cam_mode]
                            if time_value is not None:
                                status_line += f"| {datetime.datetime.now().strftime('%H:%M:%S')} | [Camera{cam_suffix} {cam_mode.upper()}]: {time_value:.0f} s | "
                        elif cam_mode == "manual" and camera_state.cameras[cam_suffix]["is_recording"]:
                            time_value = camera_state.cameras[cam_suffix]["elapsed_time"][cam_mode]
                            if time_value is not None:
                                status_line += f"| {datetime.datetime.now().strftime('%H:%M:%S')} | [Camera{cam_suffix} {cam_mode.upper()}]: {time_value:.0f} s | "

                camera_state.last_display_line = status_line
                print(f"\r{status_line}", end='', flush=True)

        # แสดงเวลาของกล้องที่กำลังรอการบันทึกในโหมดอัตโนมัติ
        elif "video_status" in payload and "Waiting for next recording" in payload["video_status"]:
            with camera_state.print_lock:
                waiting_status = ""
                for cam_suffix in ["_1", "_2"]:
                    if camera_state.cameras[cam_suffix]["is_waiting"]:
                        remaining_time = payload.get("remaining_time", 0)
                        waiting_status += f"[Camera_{cam_suffix[-1]} AUTO]: Waiting for next recording ({int(remaining_time)} s) | "

                camera_state.last_display_line = waiting_status
                print(f"\r{waiting_status}", end='', flush=True)
        
        # ถ้าไม่มี elapsed_time หรือ video_status ให้แสดงผลลัพธ์อื่นๆที่ส่งมา
        else:
            print_log(f"[RESULT] Published: {json_data}")

    # ถ้าเกิดข้อผิดพลาดในการส่งข้อมูล ให้แสดงข้อความแสดงข้อผิดพลาด
    except Exception as e:
        print_log(f"[RESULT] Failed to publish: {e}")

# ---------------- FFmpeg Process Management ----------------
def stop_ffmpeg_safely(suffix):
    camera = camera_state.cameras[suffix]
    if camera["ffmpeg_process"] and camera["ffmpeg_process"].poll() is None:
        try:
            print_log(f"[FFmpeg{suffix}] Attempting to stop process gracefully...")
            if platform.system() == "Windows":
                camera["ffmpeg_process"].send_signal(signal.CTRL_BREAK_EVENT)
            else:
                camera["ffmpeg_process"].send_signal(signal.SIGINT)
            
            start_wait = time.time()
            while camera["ffmpeg_process"].poll() is None:
                time.sleep(0.1)
                if time.time() - start_wait > 5: 
                    print_log(f"[FFmpeg{suffix}] Process taking too long to stop, killing forcefully...")
                    camera["ffmpeg_process"].kill()
                    break
            
            print_log(f"[FFmpeg{suffix}] Process stopped.")
        except Exception as e:
            print_log(f"[FFmpeg{suffix}] Error stopping process: {e}")
        finally:
            camera_state.cameras[suffix]["ffmpeg_process"] = None

def verify_video_file(video_path):
    if not os.path.exists(video_path):
        return False, "File not found"
    
    file_size = os.path.getsize(video_path)
    if file_size < 1000: 
        return False, f"File too small: {file_size} bytes"
    
    try:
        with open(video_path, 'rb') as f:
            header = f.read(8)
            if b'ftyp' not in header:
                return False, "Invalid MP4 header"
    except Exception as e:
        return False, f"Cannot read file: {e}"
    
    return True, "OK"

# ---------------- FFmpeg Command Generation ----------------
def get_ffmpeg_command(video_path, duration, rtsp_url, is_camera2=False, try_copy=True):
    command = [
        "ffmpeg",
        "-y",
        "-rtsp_transport", "tcp",
        "-timeout", "30000000"
    ]
    
    command.extend([
        "-i", rtsp_url,
        "-t", str(duration)
    ])
    
    command.extend([
        "-s", f"{VIDEO_SIZE[0]}x{VIDEO_SIZE[1]}",
        "-r", str(FPS)
    ])
    
    if try_copy:
        command.extend(["-c:v", "copy"])
    else:
        command.extend(["-c:v", "libx264"])
        
        if is_camera2:
            command.extend(["-preset", "ultrafast", "-crf", "28"])
        else:
            command.extend(["-preset", "fast", "-crf", "23"])
    
    command.extend([
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart+frag_keyframe+empty_moov",
        "-f", "mp4",
        "-an", 
        video_path
    ])
    
    return command

# ---------------- FFmpeg Recording ----------------
def record_video_ffmpeg(filename, duration, rtsp_url, suffix, stop_event):
    video_path = os.path.join(SAVE_PATH, filename)
    is_camera2 = (suffix == "_2")
    
    print_log(f"[INFO{suffix}] Attempting recording with -c:v copy")
    command = get_ffmpeg_command(video_path, duration, rtsp_url, is_camera2, try_copy=True)
    
    try:
        recording_start_time = time.time()
        
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
        camera_state.cameras[suffix]["ffmpeg_process"] = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags 
        )

        def check_stop_event():
            while not stop_event.is_set() and camera_state.cameras[suffix]["ffmpeg_process"] and camera_state.cameras[suffix]["ffmpeg_process"].poll() is None:
                time.sleep(0.1)
            
            if stop_event.is_set() and camera_state.cameras[suffix]["ffmpeg_process"] and camera_state.cameras[suffix]["ffmpeg_process"].poll() is None:
                print_log(f"[INFO{suffix}] Stop event triggered, stopping FFmpeg...")
                stop_ffmpeg_safely(suffix)

        def read_stderr():
            try:
                while (camera_state.cameras[suffix]["ffmpeg_process"] and 
                       camera_state.cameras[suffix]["ffmpeg_process"].poll() is None and
                       not stop_event.is_set()):
                    try:
                        line = camera_state.cameras[suffix]["ffmpeg_process"].stderr.readline()
                        if line:
                            line_text = line.decode(errors='ignore').strip()

                            if "Could not find tag for codec" in line_text or "Codec not supported" in line_text:
                                print_log(f"[WARNING{suffix}] Copy codec not supported, will try encoding")
                                stop_ffmpeg_safely(suffix)
                    except Exception:
                        break
                    time.sleep(0.1)
            except Exception as e:
                print_log(f"[ERROR{suffix}] stderr reader exception: {e}")

        stop_check_thread = threading.Thread(target=check_stop_event, daemon=True)
        stop_check_thread.start()

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        while camera_state.cameras[suffix]["ffmpeg_process"] and camera_state.cameras[suffix]["ffmpeg_process"].poll() is None:
            if stop_event.is_set():
                stop_ffmpeg_safely(suffix)
                break
            time.sleep(0.1)
        
        recording_time = time.time() - recording_start_time
        print_log(f"[INFO{suffix}] Actual recording time: {recording_time:.2f}s (Target: {duration}s)")
        
        is_valid, message = verify_video_file(video_path)
        
        if stop_event.is_set() and is_valid:
            print_log(f"[SUCCESS{suffix}] Video saved (stopped by timer)")
            return True

        if not is_valid or (camera_state.cameras[suffix]["ffmpeg_process"] and camera_state.cameras[suffix]["ffmpeg_process"].returncode != 0):
            if stop_event.is_set():
                print_log(f"[WARNING{suffix}] Recording stopped by timer, but file may be incomplete")
                return is_valid
                
            print_log(f"[WARNING{suffix}] Copy codec failed: {message}. Trying with encoding...")
            
            command = get_ffmpeg_command(video_path, duration, rtsp_url, is_camera2, try_copy=False)
            print_log(f"[INFO{suffix}] Retrying with encoding (libx264)")
            
            camera_state.cameras[suffix]["ffmpeg_process"] = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags 
            )
            
            stop_check_thread = threading.Thread(target=check_stop_event, daemon=True)
            stop_check_thread.start()

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            while camera_state.cameras[suffix]["ffmpeg_process"] and camera_state.cameras[suffix]["ffmpeg_process"].poll() is None:
                if stop_event.is_set():
                    stop_ffmpeg_safely(suffix)
                    break
                time.sleep(0.1)
            
            is_valid, message = verify_video_file(video_path)
            if not is_valid and not stop_event.is_set():
                print_log(f"[ERROR{suffix}] Recording failed with both methods: {message}")
                return False
        
        print_log(f"[SUCCESS{suffix}] Video saved")
        return True
        
    except Exception as e:
        print_log(f"[ERROR{suffix}] FFmpeg exception: {e}")
        return False
    finally:
        camera_state.cameras[suffix]["ffmpeg_process"] = None

# ---------------- Status Monitoring ----------------
def stream_elapsed_time(start_time, stop_event_obj, mode="manual", suffix="_0", interval=1):
    target_duration = RECORD_DURATION if mode == "auto" else LIMIT_TIME_MANUAL
    
    try:
        while not stop_event_obj.is_set():
            elapsed = round(time.time() - start_time, 2)
            remaining = max(0, target_duration - elapsed)
            
            send_result({
                "elapsed_time": elapsed,
                "remaining_time": round(remaining, 2)
            }, mode=mode, suffix=suffix)

            if elapsed >= target_duration + 5:
                print_log(f"[{mode.upper()} Mode{suffix}] Timer exceeded, stopping recording...")
                stop_event_obj.set()  
                break
                
            time.sleep(interval)
    except Exception as e:
        print_log(f"[ERROR{suffix}] Stream elapsed time error: {e}")

# ---------------- Recording Functions ----------------
def record_video(duration, rtsp_url, suffix, mode):
    mode_prefix = mode.upper()
    filename = f"video_smartfarm_{mode}{suffix}_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.mp4"
    video_path = os.path.join(SAVE_PATH, filename)
    
    print_log(f"[{mode_prefix} Mode{suffix}] Start recording: {filename}")
    send_result({
        "video_status": "Recording in process ...",
        "filename": filename,
    }, mode=mode, suffix=suffix)

    camera_state.cameras[suffix]["is_waiting"] = False
    
    start_time = time.time()
    local_stop_event = threading.Event()
    camera_state.cameras[suffix]["stop_event"] = local_stop_event

    timer_thread = threading.Thread(
        target=stream_elapsed_time,
        args=(start_time, local_stop_event, mode, suffix),
        daemon=True
    )
    timer_thread.start()

    record_thread = threading.Thread(
        target=record_video_ffmpeg,
        args=(filename, duration, rtsp_url, suffix, local_stop_event),
        daemon=True
    )
    record_thread.start()
 
    record_thread.join()

    local_stop_event.set()
    timer_thread.join(timeout=2)
    
    elapsed_time = round(time.time() - start_time, 2)
    
    print_log(f"[{mode_prefix} Mode{suffix}] Recording finished and file saved at: {video_path}")
    send_result({
        "video_status": "Recording Completed.",
        "elapsed_time": elapsed_time,
        "remaining_time": 0
    }, mode=mode, suffix=suffix)
    
    video_counts = count_videos()
    video_count = video_counts[f"{mode}_{suffix[-1]}"] if suffix in ["_1", "_2"] else 0
    send_result({"video_count": video_count}, mode=mode, suffix=suffix)

    if suffix in ["_1", "_2"]:
        camera_state.cameras[suffix]["elapsed_time"][mode] = None
    
    if mode == "manual":
        camera_state.cameras[suffix]["is_recording"] = False
        camera_state.cameras[suffix]["last_command_manual"] = None
    else:
        camera_state.cameras[suffix]["last_command_auto"] = None

def schedule_recording(rtsp_url, suffix):
    print_log(f"[AUTO Mode{suffix}] Recording started.")
    
    while camera_state.cameras[suffix]["is_schedule_running"]:
        record_video(RECORD_DURATION, rtsp_url, suffix, "auto")
        
        if not camera_state.cameras[suffix]["is_schedule_running"]: 
            break
   
        wait_start = time.time()
        camera_state.cameras[suffix]["is_waiting"] = True
        
        while time.time() - wait_start < RECORD_INTERVAL:
            if not camera_state.cameras[suffix]["is_schedule_running"]:
                break
            time.sleep(1)

            remaining = RECORD_INTERVAL - (time.time() - wait_start)
            if remaining > 0 and camera_state.cameras[suffix]["is_schedule_running"]:
                send_result({"video_status": f"Waiting for next recording: {int(remaining)} s", 
                             "remaining_time": remaining}, mode="auto", suffix=suffix)

    print_log(f"[AUTO Mode{suffix}] Recording Completed.")
    send_result({"video_status": "Recording Completed."}, mode="auto", suffix=suffix)
    camera_state.cameras[suffix]["is_waiting"] = False
    camera_state.cameras[suffix]["last_command_auto"] = None


# ---------------- System Reset Function ----------------
def reset_system():
    print_log("[SYSTEM] Reset initiated - stopping all operations")

    for suffix in ["_0", "_1", "_2"]:
        camera = camera_state.cameras[suffix]
        
        if camera["ffmpeg_process"]:
            stop_ffmpeg_safely(suffix)
    
        if camera["stop_event"]:
            camera["stop_event"].set()
  
        camera["is_schedule_running"] = False
        camera["is_recording"] = False
        camera["last_command_auto"] = None
        camera["last_command_manual"] = None
        camera["is_waiting"] = False
        
        if suffix in ["_1", "_2"]:
            camera["elapsed_time"]["auto"] = None
            camera["elapsed_time"]["manual"] = None

            send_result({
                "video_status": "System Reset",
                "elapsed_time": 0,
                "remaining_time": 0
            }, mode="auto", suffix=suffix)
            
            send_result({
                "video_status": "System Reset",
                "elapsed_time": 0,
                "remaining_time": 0
            }, mode="manual", suffix=suffix)

    camera_state.camera_ips.clear()
    camera_state.camera_urls.clear()
    
    camera_state.last_display_line = ""
    print("\033[2K\r", end='', flush=True)
    
    print_log("[SYSTEM] Reset completed - all operations stopped")

    send_result({"system_status": "Reset completed"}, mode="system", suffix="_0")

# ---------------- MQTT Callbacks ----------------
def connect_result(client, userdata, flags, rc):
    if rc == 0:
        print("\n" + "=" * 70)
        print(f"[RESULT] Connected to ThingsBoard Broker: {RESULT_BROKER}")
        print(f"[RESULT] Port: {RESULT_PORT}")
        print(f"[RESULT] Ready to publish to topic: {RESULT_TOPIC}\n")
    else:
        print(f"[RESULT] Failed to connect to ThingsBoard, rc={rc}\n")
        
def connect_command(client, userdata, flags, rc):
    if rc == 0:
        print(f"[COMMAND] Connected to MQTT Broker: {COMMAND_BROKER}")
        print(f"[COMMAND] Port: {COMMAND_PORT}")
        client.subscribe(COMMAND_TOPIC)
        print(f"[COMMAND] Subscribed to topic: {COMMAND_TOPIC}")
        print("=" * 70)
    else:
        print(f"[COMMAND] Failed to connect, rc={rc}")

def handle_camera_command(command_type, camera_id, rtsp_link):
    if camera_id:
        suffix = f"_{camera_id}"
        print_log(f"[INFO] Using specified camera ID: {camera_id}")
    else:
        suffix = get_suffix_from_rtsp(rtsp_link)
        print_log(f"[INFO] Determined camera suffix from URL: {suffix}")
    
    camera = camera_state.cameras[suffix]
    
    if camera["is_waiting"]:
        print_log(f"[{command_type.upper()} Mode{suffix}] Cannot start recording. Camera is in 'Waiting for next recording' state.")
        send_result({"video_status": "Cannot start. Camera is waiting for next recording."}, mode=command_type, suffix=suffix)
        return
    
    if rtsp_link in [False]:
        if command_type == "auto":
            if camera["is_schedule_running"]:
                camera["is_schedule_running"] = False
                print_log(f"[AUTO Mode{suffix}] Stopped scheduled recording.")
                send_result({"video_status": "Recording Stopped."}, mode="auto", suffix=suffix)
                camera["elapsed_time"]["auto"] = None
                camera["last_command_auto"] = None
                camera["is_waiting"] = False
        else: 
            if camera["is_recording"] and camera["ffmpeg_process"]:
                stop_ffmpeg_safely(suffix)  
                if camera["stop_event"]:
                    camera["stop_event"].set()
                    camera["is_recording"] = False
                print_log(f"[MANUAL Mode{suffix}] Recording completed.")
                camera["elapsed_time"]["manual"] = None
                camera["last_command_manual"] = None
        return
    
    if command_type == "auto":
        if rtsp_link == camera["last_command_auto"] and camera["is_schedule_running"]:
            print_log(f"[AUTO Mode{suffix}] Same RTSP link received and already recording, ignoring.")
            return
        camera["last_command_auto"] = rtsp_link
    else:  
        if rtsp_link == camera["last_command_manual"] and camera["is_recording"]:
            print_log(f"[MANUAL Mode{suffix}] Already recording with same RTSP.")
            return
        camera["last_command_manual"] = rtsp_link

    if not isinstance(rtsp_link, str) or not rtsp_link.startswith("rtsp"):
        print_log(f"[{command_type.upper()} Mode{suffix}] Invalid RTSP URL: {rtsp_link}")
        return
  
    if command_type == "auto":
        if camera["is_recording"]:
            print_log(f"[AUTO Mode{suffix}] Cannot start. Manual Mode is recording.")
            send_result({"video_status": "Cannot start. Manual Mode is recording."}, mode="auto", suffix=suffix)
            return
        camera["is_schedule_running"] = True
        threading.Thread(target=schedule_recording, args=(rtsp_link, suffix), daemon=True).start()
    else:  
        if camera["is_schedule_running"]:
            print_log(f"[MANUAL Mode{suffix}] Cannot start. Auto Mode is running.")
            send_result({"video_status": "Cannot start. Auto Mode is running"}, mode="manual", suffix=suffix)
            return
        if not camera["is_recording"]:
            camera["is_recording"] = True
            threading.Thread(target=record_video, args=(LIMIT_TIME_MANUAL, rtsp_link, suffix, "manual"), daemon=True).start()
        else:
            print_log(f"[MANUAL Mode{suffix}] Already recording.")

def message_command(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        if "system_reset" in data and data["system_reset"] is True:
            print_log("[COMMAND] System reset command received")
            reset_system()
            return

        if not any(key in data for key in ["camera_auto", "camera_manual", "camera_manual_1", "camera_manual_2", "camera_auto_1", "camera_auto_2"]):
            return

        print_log(f"[COMMAND] Received: {data}")
    except Exception as e:
        print_log(f"[COMMAND] Invalid JSON: {e}")
        return

    if "camera_auto" in data:
        handle_camera_command("auto", None, data["camera_auto"])
    
    if "camera_manual" in data:
        handle_camera_command("manual", None, data["camera_manual"])
    
    for camera_num in ["1", "2"]:
        auto_key = f"camera_auto_{camera_num}"
        manual_key = f"camera_manual_{camera_num}"
        
        if auto_key in data:
            handle_camera_command("auto", camera_num, data[auto_key])
            
        if manual_key in data:
            handle_camera_command("manual", camera_num, data[manual_key])

# ---------------- Video File Management ----------------
def count_videos():
    files = os.listdir(SAVE_PATH)
    count = {
        "auto_1": 0,
        "auto_2": 0,
        "manual_1": 0,
        "manual_2": 0,
    }

    for f in files:
        if f.endswith(".mp4"):
            if f.startswith("video_smartfarm_auto_1"):
                count["auto_1"] += 1
            elif f.startswith("video_smartfarm_auto_2"):
                count["auto_2"] += 1
            elif f.startswith("video_smartfarm_manual_1"):
                count["manual_1"] += 1
            elif f.startswith("video_smartfarm_manual_2"):
                count["manual_2"] += 1

    return count

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