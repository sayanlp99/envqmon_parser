import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_URL = os.getenv("PG_URL")
conn = psycopg2.connect(PG_URL)
conn.autocommit = True

def insert_device_data(device_id, data):
    with conn.cursor() as cur:
        query = """
        INSERT INTO "DeviceData" (
            device_id, temperature, humidity, pressure,
            co, methane, lpg, pm25, pm10, noise, light
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (
            device_id, data["temperature"], data["humidity"], data["pressure"],
            data["co"], data["methane"], data["lpg"], data["pm25"], data["pm10"],
            data["noise"], data["light"]
        ))
