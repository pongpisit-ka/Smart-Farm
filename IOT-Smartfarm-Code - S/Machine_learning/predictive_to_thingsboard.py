import requests
import time

url = "http://191.20.110.47:8080/api/v1/9YHHvyYocv1FEY35slEP/attributes"
headers = {"Content-Type": "application/json"}

for number in range(1, 101): 
    payload = {"predictive_value": number}
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            print(f"✅ Sent predictive_value: {number}")
        else:
            print(f"❌ Failed to send {number}: {res.status_code}")
    except Exception as e:
        print(f"❌ Error sending {number}: {e}")
    
    time.sleep(60)