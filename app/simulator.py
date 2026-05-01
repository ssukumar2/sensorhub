"""Sensor data simulator for testing without hardware."""
import math
import random
import time
import logging
import requests

log = logging.getLogger("sensorhub.simulator")

class SensorSimulator:
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend = backend_url
        self.sensors: list[dict] = []

    def register_sensors(self, count: int = 5):
        names = ["temp-indoor", "temp-outdoor", "humidity", "pressure", "voltage"]
        locations = ["living-room", "garden", "bathroom", "attic", "battery-pack"]
        for i in range(count):
            resp = requests.post(f"{self.backend}/sensors", json={
                "name": names[i % len(names)],
                "location": locations[i % len(locations)],
            })
            if resp.status_code == 200:
                self.sensors.append(resp.json())
                log.info("registered: %s", resp.json()["name"])

    def generate_value(self, sensor_name: str, tick: int) -> tuple:
        t = tick * 0.1
        if "temp" in sensor_name:
            base = 22.0 + 3.0 * math.sin(t) + random.gauss(0, 0.3)
            return round(base, 2), "celsius"
        elif "humidity" in sensor_name:
            base = 55.0 + 10.0 * math.sin(t * 0.5) + random.gauss(0, 1.0)
            return round(max(0, min(100, base)), 2), "percent"
        elif "pressure" in sensor_name:
            base = 1013.25 + 5.0 * math.sin(t * 0.3) + random.gauss(0, 0.5)
            return round(base, 2), "hpa"
        elif "voltage" in sensor_name:
            base = 12.6 - 0.01 * tick + random.gauss(0, 0.05)
            return round(max(10.0, base), 2), "voltage"
        return round(20.0 + random.gauss(0, 1), 2), "celsius"

    def run(self, interval: float = 2.0, duration: int = 60):
        log.info("starting simulation: %d sensors, %.1fs interval", len(self.sensors), interval)
        tick = 0
        end = time.time() + duration
        while time.time() < end:
            for sensor in self.sensors:
                value, unit = self.generate_value(sensor["name"], tick)
                try:
                    requests.post(f"{self.backend}/readings", json={
                        "sensor_id": sensor["id"], "value": value, "unit": unit,
                    }, headers={"x-api-key": sensor["api_key"]})
                except requests.RequestException:
                    pass
            tick += 1
            time.sleep(interval)
        log.info("simulation complete: %d ticks", tick)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sim = SensorSimulator()
    sim.register_sensors(5)
    sim.run(interval=2.0, duration=120)
