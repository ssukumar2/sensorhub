"""
Database models and request/response schemas.

Two tables:
- Sensor: a device registered with the gateway
- Reading: one telemetry data point from a sensor
"""
from datetime import datetime
from enum import Enum
from typing import Optional
import secrets

from sqlmodel import Field, SQLModel


# -------- Enums --------

class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    PRESSURE = "pressure"


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

class SensorCreate(SQLModel):
    name: str
    location: str


class ReadingCreate(SQLModel):
    sensor_id: int
    value: float
    unit: str
    sensor_type: str = "temperature"


class SensorUpdate(SQLModel):
    name: Optional[str] = None
    location: Optional[str] = None


class AlertRuleDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sensor_id: int = Field(index=True)
    metric: str = "value"
    threshold_high: Optional[float] = None
    threshold_low: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
