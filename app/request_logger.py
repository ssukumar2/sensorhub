"""Logs every incoming request with method, path, status, and duration."""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("sensorhub.requests")


class RequestLogger(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        log.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response