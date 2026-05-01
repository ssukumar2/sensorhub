"""Track firmware versions across sensor devices."""
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FirmwareInfo:
    sensor_id: int
    version: str
    build_date: str
    reported_at: datetime = None

    def __post_init__(self):
        if self.reported_at is None:
            self.reported_at = datetime.utcnow()

class FirmwareTracker:
    def __init__(self):
        self._versions: dict[int, FirmwareInfo] = {}

    def report(self, sensor_id: int, version: str, build_date: str = ""):
        self._versions[sensor_id] = FirmwareInfo(
            sensor_id=sensor_id, version=version, build_date=build_date
        )

    def get(self, sensor_id: int) -> FirmwareInfo:
        return self._versions.get(sensor_id)

    def get_all(self) -> list[FirmwareInfo]:
        return list(self._versions.values())

    def outdated(self, latest_version: str) -> list[FirmwareInfo]:
        return [fw for fw in self._versions.values() if fw.version != latest_version]

    def summary(self) -> dict:
        versions: dict[str, int] = {}
        for fw in self._versions.values():
            versions[fw.version] = versions.get(fw.version, 0) + 1
        return {"total_devices": len(self._versions), "versions": versions}

tracker = FirmwareTracker()
