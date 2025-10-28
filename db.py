import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_DEVICE_DATA_URL = os.getenv("PG_DEVICE_DATA_URL")
conn_dd = psycopg2.connect(PG_DEVICE_DATA_URL)
conn_dd.autocommit = True

PG_DEVICE_URL = os.getenv("PG_DEVICE_URL")
conn_d = psycopg2.connect(PG_DEVICE_URL)
conn_d.autocommit = True

def insert_device_data(device_id, data):
    with conn_dd.cursor() as cur:
        query = """
        INSERT INTO "DeviceData" (
            device_id, temperature, humidity, pressure,
            co, co2, methane, lpg, pm25, pm10, noise, light
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (
            device_id, data["temperature"], data["humidity"], data["pressure"],
            data["co"], data["co2"], data["methane"], data["lpg"], data["pm25"], data["pm10"],
            data["noise"], data["light"]
        ))

def get_device_id(device_name):
    with conn_d.cursor() as cur:
        query = """
        SELECT device_id FROM "devices" WHERE device_name = %s;
        """
        cur.execute(query, (device_name,))
        result = cur.fetchone()
        return result[0] if result else None
