"""Sensor tagging and grouping for fleet management."""
from dataclasses import dataclass, field

@dataclass
class SensorTag:
    key: str
    value: str

class TagRegistry:
    def __init__(self):
        self._tags: dict[int, list[SensorTag]] = {}

    def add_tag(self, sensor_id: int, key: str, value: str):
        if sensor_id not in self._tags:
            self._tags[sensor_id] = []
        existing = [t for t in self._tags[sensor_id] if t.key == key]
        if existing:
            existing[0].value = value
        else:
            self._tags[sensor_id].append(SensorTag(key=key, value=value))

    def remove_tag(self, sensor_id: int, key: str):
        if sensor_id in self._tags:
            self._tags[sensor_id] = [t for t in self._tags[sensor_id] if t.key != key]

    def get_tags(self, sensor_id: int) -> list[SensorTag]:
        return self._tags.get(sensor_id, [])

    def find_by_tag(self, key: str, value: str = None) -> list[int]:
        results = []
        for sid, tags in self._tags.items():
            for t in tags:
                if t.key == key and (value is None or t.value == value):
                    results.append(sid)
                    break
        return results

    def get_groups(self) -> dict[str, list[int]]:
        groups: dict[str, list[int]] = {}
        for sid, tags in self._tags.items():
            for t in tags:
                if t.key == "group":
                    if t.value not in groups:
                        groups[t.value] = []
                    groups[t.value].append(sid)
        return groups

registry = TagRegistry()
