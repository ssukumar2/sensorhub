"""
Database models and request/response schemas.

Two tables:
- Sensor: a device registered with the gateway
- Reading: one telemetry data point from a sensor

Kept deliberately small for day 1. We'll add authentication fields later.
"""
from datetime import datetime
from typing import Optional
import secrets

from sqlmodel import Field, SQLModel


# -------- Database tables --------

class Sensor(SQLModel, table=True):
    """A sensor registered with the gateway."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: str
    api_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Reading(SQLModel, table=True):
    """A single data point from a sensor."""
    id: Optional[int] = Field(default=None, primary_key=True)
    sensor_id: int = Field(foreign_key="sensor.id", index=True)
    value: float
    unit: str
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


# -------- Request/response schemas --------
# (separate from the table models so the API contract is explicit)

class SensorCreate(SQLModel):
    name: str
    location: str


class ReadingCreate(SQLModel):
    sensor_id: int
    value: float
    unit: str