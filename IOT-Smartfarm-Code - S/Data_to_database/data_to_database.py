import paho.mqtt.client as mqtt
import json
import datetime
from pymongo import MongoClient

# ---------------- MongoDB Config ----------------
MONGO_URI = "mongodb://admin:%40mwte%40mp%4055@191.20.110.47:27019/myDb?authSource=admin"
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["Data_From_Thingsborad"]
collection = db["Sensor_Data"]

# ---------------- MQTT Config ----------------
MQTT_BROKER = "191.20.110.47"
MQTT_PORT = 1885
MQTT_TOPIC = "/brisk" 

# ---------------- Callback เมื่อเชื่อมต่อ ----------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to: EMQX Broker, Port: {MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"Failed to connect: rc = {rc}")

# ---------------- Callback เมื่อมีข้อความ ----------------
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        data["timestamp"] = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        collection.insert_one(data)
        print(f"Saved to MongoDB from [{msg.topic}]: {data}")
    except Exception as e:
        print("Failed to save:", e)

# ---------------- MQTT Setup ----------------
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.loop_forever()
