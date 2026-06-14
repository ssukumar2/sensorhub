"""Per-sensor freeform notes registry."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class Note:
    text: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class NotesRegistry:
    def __init__(self):
        self._by_sensor: Dict[int, List[Note]] = {}

    def add(self, sensor_id: int, text: str):
        self._by_sensor.setdefault(sensor_id, []).append(Note(text=text))

    def list_for(self, sensor_id: int) -> List[dict]:
        return [
            {"text": n.text, "created_at": n.created_at.isoformat()}
            for n in self._by_sensor.get(sensor_id, [])
        ]

    def delete_all(self, sensor_id: int):
        self._by_sensor.pop(sensor_id, None)


registry = NotesRegistry()
