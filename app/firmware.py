"""Track firmware versions across sensor devices."""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class FirmwareInfo:
    sensor_id: int
    version: str
    build_date: str
    reported_at: Optional[datetime] = None

    def __post_init__(self):
        if self.reported_at is None:
            self.reported_at = datetime.utcnow()


class FirmwareTracker:
    def __init__(self):
        self._versions: Dict[int, FirmwareInfo] = {}
        self._latest_version: str = ""
        self._latest_url: str = ""

    def set_latest(self, version: str, url: str = ""):
        self._latest_version = version
        self._latest_url = url

    def latest(self) -> dict:
        return {"version": self._latest_version, "url": self._latest_url}

    def report(self, sensor_id: int, version: str, build_date: str = ""):
        self._versions[sensor_id] = FirmwareInfo(
            sensor_id=sensor_id, version=version, build_date=build_date
        )

    def get(self, sensor_id: int) -> Optional[FirmwareInfo]:
        return self._versions.get(sensor_id)

    def get_all(self) -> List[FirmwareInfo]:
        return list(self._versions.values())

    def outdated(self, latest_version: str) -> List[FirmwareInfo]:
        return [fw for fw in self._versions.values() if fw.version != latest_version]

    def summary(self) -> dict:
        versions: Dict[str, int] = {}
        for fw in self._versions.values():
            versions[fw.version] = versions.get(fw.version, 0) + 1
        return {"total_devices": len(self._versions), "versions": versions}


tracker = FirmwareTracker()
