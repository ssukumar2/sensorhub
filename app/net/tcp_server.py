"""TCP server for long-lived sensor device connections.

Protocol: newline-delimited JSON. Each line is one reading:
  {"sensor_id": 1, "value": 22.5, "unit": "celsius"}\\n

Run as: python -m app.net.tcp_server
"""
import json
import logging
import socket
import threading
from datetime import datetime
from typing import Dict

from sqlmodel import Session
from app.database import engine, init_db
from app.models import Reading, Sensor

log = logging.getLogger("sensorhub.tcp")


class TcpStats:
    def __init__(self):
        self._lock = threading.Lock()
        self.connections_opened = 0
        self.connections_closed = 0
        self.active_connections = 0
        self.readings_received = 0
        self.errors = 0
        self.last_event_at: datetime = None

    def conn_opened(self):
        with self._lock:
            self.connections_opened += 1
            self.active_connections += 1
            self.last_event_at = datetime.utcnow()

    def conn_closed(self):
        with self._lock:
            self.connections_closed += 1
            self.active_connections = max(0, self.active_connections - 1)
            self.last_event_at = datetime.utcnow()

    def reading_ok(self):
        with self._lock:
            self.readings_received += 1
            self.last_event_at = datetime.utcnow()

    def error(self):
        with self._lock:
            self.errors += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "connections_opened": self.connections_opened,
                "connections_closed": self.connections_closed,
                "active_connections": self.active_connections,
                "readings_received": self.readings_received,
                "errors": self.errors,
                "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            }


stats = TcpStats()


def parse_line(line: bytes) -> dict:
    payload = json.loads(line.decode("utf-8"))
    if not all(k in payload for k in ("sensor_id", "value", "unit")):
        raise ValueError("missing required field")
    return {
        "sensor_id": int(payload["sensor_id"]),
        "value": float(payload["value"]),
        "unit": str(payload["unit"]),
    }


def handle_client(conn: socket.socket, addr):
    stats.conn_opened()
    log.info("TCP client connected: %s", addr)
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    reading = parse_line(line)
                except (ValueError, json.JSONDecodeError) as e:
                    log.warning("bad line from %s: %s", addr, e)
                    stats.error()
                    continue
                with Session(engine) as session:
                    sensor = session.get(Sensor, reading["sensor_id"])
                    if sensor is None:
                        log.warning("unknown sensor_id=%d", reading["sensor_id"])
                        stats.error()
                        continue
                    r = Reading(sensor_id=reading["sensor_id"],
                                value=reading["value"], unit=reading["unit"])
                    session.add(r)
                    session.commit()
                stats.reading_ok()
    finally:
        conn.close()
        stats.conn_closed()
        log.info("TCP client disconnected: %s", addr)


def main(host: str = "0.0.0.0", port: int = 9200):
    init_db()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(16)
    log.info("TCP listening on %s:%d", host, port)
    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
