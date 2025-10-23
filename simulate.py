import time
import random
import json
import os
import ssl
import requests
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import math

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
    "TEST":     {"temp_offset": 2,  "humidity_offset": 5,  "noise_offset": 5,  "pm25_offset": 5,  "co_offset": 0.3, "lpg_offset": 2},
    "TEST1":     {"temp_offset": -1, "humidity_offset": 0,  "noise_offset": -10,"pm25_offset": 0,  "co_offset": 0.0, "lpg_offset": 0},
    "TEST3":    {"temp_offset": 0,  "humidity_offset": 0,  "noise_offset": 0,  "pm25_offset": 2,  "co_offset": 0.1, "lpg_offset": 0.5},
    "TEST4":    {"temp_offset": 1,  "humidity_offset": -5, "noise_offset": 3,  "pm25_offset": 20, "co_offset": 0.5, "lpg_offset": 0.2},
    "TEST5":    {"temp_offset": 0.5,"humidity_offset": 2,  "noise_offset": 2,  "pm25_offset": 3,  "co_offset": 0.1, "lpg_offset": 0.3}
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

def compute_profiles(hour_f, season):
    """Return target ranges for parameters based on time and season."""
    profiles = {
        "summer": {"pm25": (80, 150)},
        "monsoon": {"pm25": (30, 60)},
        "winter": {"pm25": (50, 100)}
    }
    p = profiles[season]

    # Smooth light using sine wave during daytime
    if 6 <= hour_f <= 18:
        day_frac = (hour_f - 6) / 12
        light = 50 + 950 * math.sin(math.pi * day_frac)
    else:
        light = 50

    # Noise levels with slight smoothing via hour_f
    noise = 40
    if 7 <= hour_f < 9 or 17 <= hour_f < 20:
        noise = 80
    elif 10 <= hour_f < 16:
        noise = 60

    # Fixed mid-range for PM, no random for smoothness
    pm25 = (p["pm25"][0] + p["pm25"][1]) / 2
    pm10 = pm25 + 30

    return {
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
    last_fetch_time = time.time()

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
            hour_f = now.hour + now.minute / 60.0

            # Fetch weather every 60 seconds for realistic gradual updates
            current_time = time.time()
            if current_time - last_fetch_time > 60:
                baseline = fetch_weather()
                last_fetch_time = current_time

            profile = compute_profiles(hour_f, season)

            for dev, offsets in DEVICES.items():
                states[dev]["temperature"] = drift(states[dev]["temperature"], baseline["temperature"] + offsets["temp_offset"], noise=0.1)
                states[dev]["humidity"] = drift(states[dev]["humidity"], baseline["humidity"] + offsets["humidity_offset"], noise=0.2)
                states[dev]["pressure"] = drift(states[dev]["pressure"], baseline["pressure"], noise=0.1)
                states[dev]["light"] = drift(states[dev]["light"], profile["light"], noise=1)
                states[dev]["noise"] = drift(states[dev]["noise"], profile["noise"] + offsets["noise_offset"], noise=0.5)
                states[dev]["pm25"] = drift(states[dev]["pm25"], profile["pm25"] + offsets["pm25_offset"], noise=0.5)
                states[dev]["pm10"] = drift(states[dev]["pm10"], profile["pm10"] + offsets["pm25_offset"], noise=1)

                states[dev]["co"] = drift(states[dev]["co"], 1.0 + offsets["co_offset"], noise=0.01)
                states[dev]["methane"] = drift(states[dev]["methane"], 100, noise=1)
                states[dev]["lpg"] = drift(states[dev]["lpg"], 100 + offsets["lpg_offset"], noise=1)

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