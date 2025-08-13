import time
import random
import json
import os
import ssl
import requests
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", 1883))
mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
use_tls = os.getenv("MQTT_USE_TLS", "false").lower() == "true"
ca_cert_path = os.getenv("MQTT_CA_CERT_PATH", "")

PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", 5))
LOCATION = {"lat": 12.9716, "lon": 77.5946}  # Bangalore

# Device definitions
DEVICES = {
    "7bcf5f30-e209-4751-bbdf-e5c2327577cc":     {"temp_offset": 2,  "humidity_offset": 5,  "noise_offset": 5,  "pm25_offset": 5,  "co_offset": 0.3, "lpg_offset": 2},
    "c755fc04-4ded-4e9a-a1ef-de7eb4c95514":     {"temp_offset": -1, "humidity_offset": 0,  "noise_offset": -10,"pm25_offset": 0,  "co_offset": 0.0, "lpg_offset": 0},
    "566ed335-beb7-4973-8c7c-324346b28533":    {"temp_offset": 0,  "humidity_offset": 0,  "noise_offset": 0,  "pm25_offset": 2,  "co_offset": 0.1, "lpg_offset": 0.5},
    "7d042394-f964-4293-9f18-ef706ca00b13":    {"temp_offset": 1,  "humidity_offset": -5, "noise_offset": 3,  "pm25_offset": 20, "co_offset": 0.5, "lpg_offset": 0.2},
    "2a571118-000a-419f-8e96-092f295a1518":    {"temp_offset": 0.5,"humidity_offset": 2,  "noise_offset": 2,  "pm25_offset": 3,  "co_offset": 0.1, "lpg_offset": 0.3}
}

def fetch_weather():
    """Fetch current weather for Bangalore using Open-Meteo (no API key)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={LOCATION['lat']}&longitude={LOCATION['lon']}&current_weather=true"
        f"&hourly=relativehumidity_2m,pressure_msl"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        cur = data["current_weather"]
        humidity = data["hourly"]["relativehumidity_2m"][0]
        pressure = data["hourly"]["pressure_msl"][0]
        return {
            "temperature": cur["temperature"],
            "humidity": humidity,
            "pressure": pressure
        }
    except Exception as e:
        print(f"⚠️ Weather fetch failed: {e}")
        return {"temperature": 25.0, "humidity": 70.0, "pressure": 1010.0}

def get_season(month):
    """Return current season for Bangalore."""
    if 3 <= month <= 5:
        return "summer"
    elif 6 <= month <= 9:
        return "monsoon"
    else:
        return "winter"

def compute_profiles(hour, season):
    """Return target ranges for parameters based on time and season."""
    profiles = {
        "summer": {"temp_min": 20, "temp_max": 35, "humidity_min": 40, "humidity_max": 60, "pm25": (80, 150)},
        "monsoon": {"temp_min": 19, "temp_max": 28, "humidity_min": 70, "humidity_max": 90, "pm25": (30, 60)},
        "winter": {"temp_min": 15, "temp_max": 27, "humidity_min": 50, "humidity_max": 70, "pm25": (50, 100)}
    }
    p = profiles[season]

    if 6 <= hour <= 18:
        frac = (hour - 6) / 12
        target_temp = p["temp_min"] + (p["temp_max"] - p["temp_min"]) * frac
    else:
        target_temp = p["temp_min"]

    target_humidity = p["humidity_max"] if hour < 6 or hour > 20 else p["humidity_min"]
    target_pressure = 1010 + random.uniform(-5, 5)

    if 6 <= hour <= 18:
        light = 100 + (hour - 6) * 80
    else:
        light = 50

    noise = 40
    if 7 <= hour <= 9 or 17 <= hour <= 20:
        noise = 80
    elif 10 <= hour <= 16:
        noise = 60

    pm25_range = p["pm25"]
    pm25 = random.uniform(*pm25_range)
    pm10 = pm25 + random.uniform(10, 50)

    return {
        "temperature": target_temp,
        "humidity": target_humidity,
        "pressure": target_pressure,
        "light": light,
        "noise": noise,
        "pm25": pm25,
        "pm10": pm10
    }

def drift(current, target, noise=0.5):
    """Move value toward target with small noise."""
    return round(current + (target - current) * 0.05 + random.uniform(-noise, noise), 2)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker.")
    else:
        print(f"❌ Failed to connect: code {rc}")

def simulate():
    season = get_season(datetime.now().month)
    print(f"🌦 Season: {season}")
    baseline = fetch_weather()

    # Initialize each device state
    states = {}
    for dev, offsets in DEVICES.items():
        states[dev] = {
            "temperature": baseline["temperature"] + offsets["temp_offset"],
            "humidity": baseline["humidity"] + offsets["humidity_offset"],
            "pressure": baseline["pressure"],
            "co": random.uniform(0.1, 1.0) + offsets["co_offset"],
            "methane": random.uniform(10, 200),
            "lpg": random.uniform(10, 200) + offsets["lpg_offset"],
            "pm25": random.uniform(30, 80) + offsets["pm25_offset"],
            "pm10": random.uniform(50, 120) + offsets["pm25_offset"],
            "noise": 50 + offsets["noise_offset"],
            "light": 200
        }

    client = mqtt.Client(client_id=f"sim_multi_device", protocol=mqtt.MQTTv311)
    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)

    # Updated TLS handling — works even if CA cert path is missing
    if use_tls:
        try:
            if ca_cert_path and os.path.exists(ca_cert_path):
                client.tls_set(ca_certs=ca_cert_path, tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(False)
                print(f"🔒 TLS enabled with CA cert: {ca_cert_path}")
            else:
                client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(True)
                print("🔒 TLS enabled without CA cert (insecure mode).")
        except Exception as e:
            print(f"⚠️ Failed to configure TLS ({e}), continuing without TLS.")

    client.on_connect = on_connect
    client.connect(mqtt_broker, mqtt_port, 60)
    client.loop_start()

    try:
        while True:
            now = datetime.now()
            profile = compute_profiles(now.hour, season)

            for dev, offsets in DEVICES.items():
                states[dev]["temperature"] = drift(states[dev]["temperature"], profile["temperature"] + offsets["temp_offset"], noise=0.2)
                states[dev]["humidity"] = drift(states[dev]["humidity"], profile["humidity"] + offsets["humidity_offset"], noise=0.5)
                states[dev]["pressure"] = drift(states[dev]["pressure"], profile["pressure"], noise=0.2)
                states[dev]["light"] = drift(states[dev]["light"], profile["light"], noise=10)
                states[dev]["noise"] = drift(states[dev]["noise"], profile["noise"] + offsets["noise_offset"], noise=2)
                states[dev]["pm25"] = drift(states[dev]["pm25"], profile["pm25"] + offsets["pm25_offset"], noise=3)
                states[dev]["pm10"] = drift(states[dev]["pm10"], profile["pm10"] + offsets["pm25_offset"], noise=5)

                states[dev]["co"] = drift(states[dev]["co"], 1.0 + offsets["co_offset"], noise=0.1)
                states[dev]["methane"] = drift(states[dev]["methane"], 100, noise=5)
                states[dev]["lpg"] = drift(states[dev]["lpg"], 100 + offsets["lpg_offset"], noise=5)

                states[dev]["recorded_at"] = int(time.time())

                payload = json.dumps(states[dev])
                topic = f"envqmon/{dev}"
                client.publish(topic, payload, qos=1, retain=False)
                print(f"📤 {now} [{dev}] → {payload}")

            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped.")
        client.loop_stop()

if __name__ == "__main__":
    simulate()
