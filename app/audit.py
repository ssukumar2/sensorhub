"""Append-only audit log for hub admin actions."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class AuditEntry:
    action: str
    target: str
    detail: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AuditLog:
    def __init__(self, max_entries: int = 1000):
        self._entries: List[AuditEntry] = []
        self._max = max_entries

    def record(self, action: str, target: str, detail: Optional[dict] = None):
        self._entries.append(AuditEntry(action=action, target=target, detail=detail or {}))
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max:]

    def recent(self, limit: int = 50) -> List[dict]:
        return [
            {"action": e.action, "target": e.target, "detail": e.detail,
             "timestamp": e.timestamp.isoformat()}
            for e in self._entries[-limit:][::-1]
        ]


log = AuditLog()
