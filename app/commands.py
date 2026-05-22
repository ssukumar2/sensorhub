"""Hub-to-device command queue for fleet management."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import uuid


@dataclass
class Command:
    id: str
    sensor_id: int
    type: str
    payload: dict
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    acked_at: Optional[datetime] = None
    result: Optional[str] = None


class CommandQueue:
    def __init__(self):
        self._queue: Dict[int, List[Command]] = {}
        self._by_id: Dict[str, Command] = {}

    def enqueue(self, sensor_id: int, type: str, payload: dict) -> Command:
        cmd = Command(id=str(uuid.uuid4()), sensor_id=sensor_id, type=type, payload=payload)
        self._queue.setdefault(sensor_id, []).append(cmd)
        self._by_id[cmd.id] = cmd
        return cmd

    def pending_for(self, sensor_id: int) -> List[Command]:
        return [c for c in self._queue.get(sensor_id, []) if c.status == "pending"]

    def mark_delivered(self, cmd_id: str):
        c = self._by_id.get(cmd_id)
        if c:
            c.status = "delivered"
            c.delivered_at = datetime.utcnow()

    def ack(self, cmd_id: str, result: str = ""):
        c = self._by_id.get(cmd_id)
        if c:
            c.status = "acked"
            c.acked_at = datetime.utcnow()
            c.result = result

    def get(self, cmd_id: str) -> Optional[Command]:
        return self._by_id.get(cmd_id)

    def all_for(self, sensor_id: int) -> List[Command]:
        return list(self._queue.get(sensor_id, []))


queue = CommandQueue()
