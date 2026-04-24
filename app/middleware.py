"""Simple in-memory rate limiter for API endpoints."""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self.clients = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        now = time.time()

        self.clients[client_ip] = [
            t for t in self.clients[client_ip]
            if now - t < self.window
        ]

        if len(self.clients[client_ip]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="too many requests")

        self.clients[client_ip].append(now)
        return await call_next(request)