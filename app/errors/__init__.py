"""Custom error types for sensorhub."""

from fastapi import HTTPException


class SensorNotFoundError(HTTPException):
    def __init__(self, sensor_id: int):
        super().__init__(
            status_code=404,
            detail=f"sensor {sensor_id} not found"
        )


class InvalidApiKeyError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="invalid api key"
        )


class StaleTimestampError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="timestamp too old"
        )


class InvalidSignatureError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="invalid signature"
        )


class MissingHeaderError(HTTPException):
    def __init__(self, header_name: str):
        super().__init__(
            status_code=400,
            detail=f"missing required header: {header_name}"
        )