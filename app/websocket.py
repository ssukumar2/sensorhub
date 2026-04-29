"""WebSocket endpoint for real-time sensor reading updates."""
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("sensorhub.ws")

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        log.info("ws client connected, total=%d", len(self.active))

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        log.info("ws client disconnected, total=%d", len(self.active))

    async def broadcast(self, data: dict):
        message = json.dumps(data)
        disconnected = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.active.remove(ws)

manager = ConnectionManager()

async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
