import cv2
import shutil
import os
import time
from datetime import datetime

Camera_Num = 1

def test_codecs():
    test_file = "test.avi"
    codecs = [
        ('XVID', cv2.VideoWriter_fourcc(*'XVID')),
        ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')), 
        ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),
        ('DIVX', cv2.VideoWriter_fourcc(*'DIVX')),
    ]
    
    working_codecs = []
    for name, fourcc in codecs:
        out = cv2.VideoWriter(test_file, fourcc, 20.0, (640, 480))
        if out.isOpened():
            working_codecs.append((name, fourcc))
            print(f"{name} - ใช้ได้")
            out.release()
            if os.path.exists(test_file):
                os.remove(test_file)
        else:
            print(f"{name} - ใช้ไม่ได้")
    
    return working_codecs

print("ทดสอบ codec ที่ใช้ได้:")
available_codecs = test_codecs()

if not available_codecs:
    print("ไม่มี codec ที่ใช้ได้")
    exit()

codec_name, fourcc = available_codecs[0]
print(f"จะใช้ codec: {codec_name}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"smartfarm_{timestamp}.mp4" 

local_temp = "C:/temp/smartfarm/"
os.makedirs(local_temp, exist_ok=True)
local_file = os.path.join(local_temp, filename)

final_path = r"R:\01-Organize\01-Management\01-Data Center\Brisk\06-AI & Machine Learning (D0340)\04-IOT_Smartfarm\video_smartfarm"
os.makedirs(final_path, exist_ok=True)
final_file = os.path.join(final_path, filename)

cap = cv2.VideoCapture(Camera_Num)

if not cap.isOpened():
    print("ไม่สามารถเข้าถึงเว็บแคมได้")
else:
    print("เข้าถึงเว็บแคมสำเร็จ")
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)  
    
    out = cv2.VideoWriter(local_file, fourcc, 20.0, (3840, 2160))
    
    if not out.isOpened():
        print("ไม่สามารถสร้าง VideoWriter ได้")
        cap.release()
        exit()
    
    print(f"กำลังบันทึกที่: {local_file}")
    print("กำลังบันทึกวิดีโอเป็นเวลา 60 วินาที")
    print("กด 'q' เพื่อหยุดบันทึกก่อนเวลา")

    frame_count = 0
    start_time = time.time()
    recording_duration = 60  
    
    while(True):
        ret, frame = cap.read()
        if ret:
            resize_frame = cv2.resize(frame, (3840, 2160))  
            out.write(resize_frame)
            
            frame_count += 1

            if (time.time() - start_time) >= recording_duration:
                break
        else:
            print("ไม่สามารถอ่านเฟรมได้")
            break

    cap.release()
    out.release()  
    cv2.destroyAllWindows()
    
    actual_duration = time.time() - start_time
    print(f"บันทึกเสร็จสิ้น ระยะเวลาบันทึก: {actual_duration:.0f} วินาที")

    if os.path.exists(local_file):
        print(f"พบไฟล์: {local_file}")
        print(f"ขนาดไฟล์: {os.path.getsize(local_file)/1024/1024:.2f} MB")
        print("กำลังย้ายไฟล์ไป R drive...")
        
        try:
            if os.path.exists(os.path.dirname(final_file)):
                shutil.copy2(local_file, final_file)
                print(f"Copy สำเร็จ! ไฟล์อยู่ที่: {final_file}")
                os.remove(local_file)
                print("ลบไฟล์ชั่วคราวแล้ว")
            else:
                print(f"ไม่สามารถเข้าถึง R drive")
                print(f"ไฟล์ยังอยู่ที่: {local_file}")
        except Exception as e:
            print(f"เกิดข้อผิดพลาด: {e}")
            print(f"ไฟล์ยังอยู่ที่: {local_file}")