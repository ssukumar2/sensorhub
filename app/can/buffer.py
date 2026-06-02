"""In-memory ring buffer of recently received CAN frames for the HTTP API."""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, List


@dataclass
class FrameRecord:
    can_id: int
    sensor_id: int
    value: float
    unit: str
    received_at: datetime = field(default_factory=datetime.utcnow)


class FrameBuffer:
    def __init__(self, max_size: int = 500):
        self._buf = deque(maxlen=max_size)
        self._lock = Lock()
        self._frame_count = 0
        self._error_count = 0
        self._by_sensor: Dict[int, int] = {}

    def record(self, can_id: int, sensor_id: int, value: float, unit: str):
        with self._lock:
            self._buf.append(FrameRecord(can_id=can_id, sensor_id=sensor_id,
                                          value=value, unit=unit))
            self._frame_count += 1
            self._by_sensor[sensor_id] = self._by_sensor.get(sensor_id, 0) + 1

    def record_error(self):
        with self._lock:
            self._error_count += 1

    def recent(self, limit: int = 50) -> List[dict]:
        with self._lock:
            items = list(self._buf)[-limit:][::-1]
        return [
            {"can_id": f"0x{f.can_id:X}", "sensor_id": f.sensor_id,
             "value": f.value, "unit": f.unit,
             "received_at": f.received_at.isoformat()}
            for f in items
        ]

    def stats(self) -> dict:
        with self._lock:
            return {
                "frames_received": self._frame_count,
                "errors": self._error_count,
                "buffer_size": len(self._buf),
                "per_sensor": dict(self._by_sensor),
            }


buffer = FrameBuffer()
