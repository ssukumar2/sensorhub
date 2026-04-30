"""Prometheus-compatible metrics endpoint."""
import time
from dataclasses import dataclass, field
from threading import Lock

@dataclass
class Metrics:
    requests_total: int = 0
    readings_total: int = 0
    sensors_total: int = 0
    errors_total: int = 0
    start_time: float = field(default_factory=time.time)
    _lock: Lock = field(default_factory=Lock)

    def inc_requests(self):
        with self._lock:
            self.requests_total += 1

    def inc_readings(self, count: int = 1):
        with self._lock:
            self.readings_total += count

    def inc_sensors(self):
        with self._lock:
            self.sensors_total += 1

    def inc_errors(self):
        with self._lock:
            self.errors_total += 1

    def uptime(self) -> float:
        return time.time() - self.start_time

    def to_prometheus(self) -> str:
        lines = [
            f"# HELP sensorhub_requests_total Total HTTP requests",
            f"# TYPE sensorhub_requests_total counter",
            f"sensorhub_requests_total {self.requests_total}",
            f"# HELP sensorhub_readings_total Total readings ingested",
            f"# TYPE sensorhub_readings_total counter",
            f"sensorhub_readings_total {self.readings_total}",
            f"# HELP sensorhub_sensors_total Total registered sensors",
            f"# TYPE sensorhub_sensors_total gauge",
            f"sensorhub_sensors_total {self.sensors_total}",
            f"# HELP sensorhub_errors_total Total errors",
            f"# TYPE sensorhub_errors_total counter",
            f"sensorhub_errors_total {self.errors_total}",
            f"# HELP sensorhub_uptime_seconds Uptime in seconds",
            f"# TYPE sensorhub_uptime_seconds gauge",
            f"sensorhub_uptime_seconds {self.uptime():.1f}",
        ]
        return "\n".join(lines) + "\n"

metrics = Metrics()
