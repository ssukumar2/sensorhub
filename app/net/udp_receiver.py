"""UDP receiver for lightweight sensor reporting.

Datagram format (JSON):
  {"sensor_id": 1, "value": 22.5, "unit": "celsius"}

Run as: python -m app.net.udp_receiver
"""
import json
import logging
import socket
import threading
from datetime import datetime
from typing import Dict, List

from sqlmodel import Session
from app.database import engine, init_db
from app.models import Reading, Sensor

log = logging.getLogger("sensorhub.udp")


class UdpStats:
    """Thread-safe counters for the UDP receiver."""
    def __init__(self):
        self._lock = threading.Lock()
        self.packets = 0
        self.errors = 0
        self.bytes = 0
        self.last_packet_at: datetime = None
        self.by_sensor: Dict[int, int] = {}

    def record_packet(self, size: int, sensor_id: int):
        with self._lock:
            self.packets += 1
            self.bytes += size
            self.last_packet_at = datetime.utcnow()
            self.by_sensor[sensor_id] = self.by_sensor.get(sensor_id, 0) + 1

    def record_error(self):
        with self._lock:
            self.errors += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "packets": self.packets,
                "errors": self.errors,
                "bytes_received": self.bytes,
                "last_packet_at": self.last_packet_at.isoformat() if self.last_packet_at else None,
                "per_sensor": dict(self.by_sensor),
            }


stats = UdpStats()


def decode_datagram(data: bytes) -> dict:
    payload = json.loads(data.decode("utf-8"))
    if not all(k in payload for k in ("sensor_id", "value", "unit")):
        raise ValueError("missing required field")
    return {
        "sensor_id": int(payload["sensor_id"]),
        "value": float(payload["value"]),
        "unit": str(payload["unit"]),
    }


def main(host: str = "0.0.0.0", port: int = 9100):
    init_db()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    log.info("UDP listening on %s:%d", host, port)
    while True:
        data, addr = sock.recvfrom(2048)
        try:
            reading = decode_datagram(data)
        except (ValueError, json.JSONDecodeError) as e:
            log.warning("bad datagram from %s: %s", addr, e)
            stats.record_error()
            continue
        with Session(engine) as session:
            sensor = session.get(Sensor, reading["sensor_id"])
            if sensor is None:
                log.warning("unknown sensor_id=%d", reading["sensor_id"])
                stats.record_error()
                continue
            r = Reading(sensor_id=reading["sensor_id"],
                        value=reading["value"], unit=reading["unit"])
            session.add(r)
            session.commit()
        stats.record_packet(len(data), reading["sensor_id"])
        log.info("UDP %s -> sensor=%d %.2f %s",
                 addr, reading["sensor_id"], reading["value"], reading["unit"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
