from dataclasses import dataclass

@dataclass
class SensorData:
    temperature: float
    humidity: float
    pressure: float
    co: float
    methane: float
    lpg: float
    pm25: float
    pm10: float
    noise: float
    light: float
