import time
import random
import json
import os
import ssl
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from datetime import datetime

load_dotenv()

# Device and MQTT Config
device_id = os.getenv("DEVICE_ID", "testdevice123")
topic = f"envqmon/{device_id}"

mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", 1883))
mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
use_tls = os.getenv("MQTT_USE_TLS", "false").lower() == "true"
ca_cert_path = os.getenv("MQTT_CA_CERT_PATH", "")

def generate_sensor_data():
    return {
        "temperature": round(random.uniform(20.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 70.0), 2),
        "pressure": round(random.uniform(950.0, 1050.0), 2),
        "co": round(random.uniform(0.0, 5.0), 2),
        "methane": round(random.uniform(0.0, 1000.0), 2),
        "lpg": round(random.uniform(0.0, 1000.0), 2),
        "pm25": round(random.uniform(0.0, 500.0), 2),
        "pm10": round(random.uniform(0.0, 500.0), 2),
        "noise": round(random.uniform(30.0, 90.0), 2),
        "light": round(random.uniform(100.0, 1000.0), 2),
        "recorded_at": int(time.time())
    }

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker.")
    else:
        print(f"❌ Failed to connect: code {rc}")

def simulate():
    client = mqtt.Client(client_id=f"sim_{device_id}", protocol=mqtt.MQTTv311)

    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)

    if use_tls and ca_cert_path:
        client.tls_set(ca_certs=ca_cert_path, tls_version=ssl.PROTOCOL_TLSv1_2)

    client.on_connect = on_connect
    client.connect(mqtt_broker, mqtt_port, 60)
    client.loop_start()

    try:
        while True:
            payload = generate_sensor_data()
            client.publish(topic, json.dumps(payload), qos=1)
            print(f"📤 Published to {topic}: {payload}")
            time.sleep(5)  # interval in seconds
    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped.")
        client.loop_stop()

if __name__ == "__main__":
    simulate()
