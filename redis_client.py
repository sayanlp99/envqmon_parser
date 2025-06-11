import os
import redis
from dotenv import load_dotenv

load_dotenv()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    username=os.getenv("REDIS_USERNAME", None),
    password=os.getenv("REDIS_PASSWORD", None),
)

def update_live_data(device_id, payload):
    redis_key = f"live_{device_id}"
    redis_client.set(redis_key, payload)  # no TTL
