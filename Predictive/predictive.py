import requests
import time
import random

broker = "191.20.110.47"
port = "8080"
access_token = "predictive_token"

url = f"http://{broker}:{port}/api/v1/{access_token}/attributes"

headers = {"Content-Type": "application/json"}

def random_value(min_val, max_val):
    return random.randint(min_val, max_val)

num_iterations = 200

for i in range(num_iterations):
    plant_data = {
        "water_volume": random_value(10, 100),      
        "watering_frequency": random_value(1, 24),  
        "soaking_time": random_value(1, 24),       
        "weight_press": random_value(100, 1000),    
        "light": random_value(0, 100),   
        "temp": random_value(0, 100),  
        "humidity": random_value(0, 100),
    }
    
    try:
        res = requests.post(url, headers=headers, json=plant_data)
        if res.status_code == 200:
            print(f"✅ ครั้งที่ {i+1}: ส่งข้อมูลสำเร็จ: {plant_data}")
        else:
            print(f"❌ ครั้งที่ {i+1}: ส่งข้อมูลไม่สำเร็จ: {res.status_code}")
    except Exception as e:
        print(f"❌ ครั้งที่ {i+1}: เกิดข้อผิดพลาด: {e}")
    
    time.sleep(60)

print("การทดสอบส่งข้อมูลเสร็จสิ้น")
