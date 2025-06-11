import os
import json
import ssl
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from db import insert_device_data
from redis_client import update_live_data

load_dotenv()

# MQTT Config from .env
broker = os.getenv("MQTT_BROKER", "localhost")
port = int(os.getenv("MQTT_PORT", 1883))
client_id = os.getenv("MQTT_CLIENT_ID", "python_mqtt_ingestor")
mqtt_username = os.getenv("MQTT_USERNAME", "")
mqtt_password = os.getenv("MQTT_PASSWORD", "")
use_tls = os.getenv("MQTT_USE_TLS", "false").lower() == "true"
ca_cert_path = os.getenv("MQTT_CA_CERT_PATH", "")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker successfully.")
        client.subscribe("envqmon/+")
    else:
        print(f"❌ Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()

    print(f"📥 Message from {topic}: {payload}")

    try:
        device_id = topic.split("/")[1]
        data = json.loads(payload)

        insert_device_data(device_id, data)
        update_live_data(device_id, payload)

    except Exception as e:
        print(f"❗ Error processing message: {e}")

def start_mqtt():
    client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)

    if use_tls and ca_cert_path:
        client.tls_set(
            ca_certs=ca_cert_path,
            certfile=None,
            keyfile=None,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker, port, 60)
        client.loop_forever()
    except Exception as e:
        print(f"❌ Failed to connect to MQTT broker: {e}")
