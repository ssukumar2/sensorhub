"""Sensor data simulator for testing without hardware."""
import json
import math
import random
import time
import logging
import requests

from app.security import compute_hmac_signed, generate_nonce

log = logging.getLogger("sensorhub.simulator")


class SensorSimulator:
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend = backend_url
        self.sensors: list = []

    def register_sensors(self, count: int = 5):
        names = ["temp-indoor", "temp-outdoor", "humidity", "pressure", "voltage"]
        locations = ["living-room", "garden", "bathroom", "attic", "battery-pack"]
        for i in range(count):
            resp = requests.post(f"{self.backend}/sensors", json={
                "name": names[i % len(names)],
                "location": locations[i % len(locations)],
            })
            if resp.status_code in (200, 201):
                self.sensors.append(resp.json())
                log.info("registered: %s", resp.json()["name"])

    def generate_value(self, sensor_name: str, tick: int):
        t = tick * 0.1
        if "temp" in sensor_name:
            return round(22.0 + 3.0 * math.sin(t) + random.gauss(0, 0.3), 2), "celsius"
        elif "humidity" in sensor_name:
            return round(max(0, min(100, 55.0 + 10.0 * math.sin(t * 0.5) + random.gauss(0, 1.0))), 2), "percent"
        elif "pressure" in sensor_name:
            return round(1013.25 + 5.0 * math.sin(t * 0.3) + random.gauss(0, 0.5), 2), "hpa"
        elif "voltage" in sensor_name:
            return round(max(10.0, 12.6 - 0.01 * tick + random.gauss(0, 0.05)), 2), "voltage"
        return round(20.0 + random.gauss(0, 1), 2), "celsius"

    def _post_signed(self, path: str, body_obj, api_key: str):
        body = json.dumps(body_obj, separators=(",", ":"))
        nonce = generate_nonce()
        timestamp = str(int(time.time()))
        signature = compute_hmac_signed(api_key, body, nonce, timestamp)
        return requests.post(
            f"{self.backend}{path}",
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "x-nonce": nonce,
                "x-timestamp": timestamp,
                "x-signature": signature,
            },
        )

    def run(self, interval: float = 2.0, duration: int = 60):
        log.info("starting simulation: %d sensors, %.1fs interval", len(self.sensors), interval)
        tick = 0
        end = time.time() + duration
        while time.time() < end:
            for sensor in self.sensors:
                value, unit = self.generate_value(sensor["name"], tick)
                try:
                    self._post_signed(
                        "/readings",
                        {"sensor_id": sensor["id"], "value": value, "unit": unit},
                        sensor["api_key"],
                    )
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