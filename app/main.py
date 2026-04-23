"""
SensorHUb — secure sensor network gateway.

"""
import secrets
from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import (
    Sensor,
    Reading,
    SensorCreate,
    ReadingCreate,
)
from app.middleware import RateLimiter

import time as _time

_start_time = _time.time()
_request_count = 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the app starts. Creates the SQLite tables if they don't exist.
    init_db()
    yield
    # Nothing to clean up for now.


app = FastAPI(
    title="Sensor_HUB",
    description="Secure sensor network gateway — telemetry ingestion and query API.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RateLimiter, max_requests=100, window_seconds=60)

# -------- Health check --------

@app.get("/health")
def health():
    """Simple liveness probe. Useful for Docker/Kubernetes later."""
    return {"status": "ok", "service": "sensorhub", "version": "0.1.0"}

def require_sensor_key(
    sensor_id: int,
    x_api_key: str = Header(..., description="Sensor API key"),
    session: Session = Depends(get_session),
) -> Sensor:
    """Verify the API key matches the sensor. Returns the sensor on success."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    return sensor

@app.get("/metrics")
def metrics():
    """Basic server metrics for monitoring."""
    global _request_count
    _request_count += 1
    uptime = int(_time.time() - _start_time)
    return {
        "uptime_seconds": uptime,
        "request_count": _request_count,
        "service": "sensorhub",
    }

# -------- Sensors --------

@app.post("/sensors", response_model=Sensor, status_code=201)
def register_sensor(
    payload: SensorCreate,
    session: Session = Depends(get_session),
):
    """Register a new sensor with the gateway."""
    sensor = Sensor(name=payload.name, location=payload.location)
    session.add(sensor)
    session.commit()
    session.refresh(sensor)
    return sensor


@app.get("/sensors", response_model=List[Sensor])
def list_sensors(session: Session = Depends(get_session)):
    """List all registered sensors."""
    return session.exec(select(Sensor)).all()


@app.get("/sensors/{sensor_id}", response_model=Sensor)
def get_sensor(sensor_id: int, session: Session = Depends(get_session)):
    """Get one sensor by ID."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    return sensor


# -------- Readings --------

@app.post("/readings", response_model=Reading, status_code=201)
def submit_reading(
    payload: ReadingCreate,
    #sensor: Sensor = Depends(require_sensor_key),
    x_api_key: str = Header(..., description="Sensor API key"),
    session: Session = Depends(get_session),
):
    """Submit a telemetry reading from a sensor."""
    # Check the sensor exists before inserting the reading.
    #sensor = session.get(Sensor, payload.sensor_id)
    #if sensor is None:
      #  raise HTTPException(status_code=404, detail="sensor not found")

    sensor = session.get(Sensor, payload.sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")

    reading = Reading(
        sensor_id=payload.sensor_id,
        value=payload.value,
        unit=payload.unit,
    )
    session.add(reading)
    session.commit()
    session.refresh(reading)
    return reading


@app.get("/sensors/{sensor_id}/readings", response_model=List[Reading])
def list_readings_for_sensor(
    sensor_id: int,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List recent readings for a sensor, most recent first."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")

    statement = (
        select(Reading)
        .where(Reading.sensor_id == sensor_id)
        .order_by(Reading.recorded_at.desc())
        .limit(limit)
    )
    return session.exec(statement).all()


@app.post("/readings/batch", status_code=201)
def submit_batch_readings(
    readings: List[ReadingCreate],
    x_api_key: str = Header(..., description="Sensor API key"),
    session: Session = Depends(get_session),
):
    """Submit multiple readings in a single request."""
    if not readings:
        raise HTTPException(status_code=400, detail="empty batch")

    sensor = session.get(Sensor, readings[0].sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")

    created = []
    for r in readings:
        reading = Reading(sensor_id=r.sensor_id, value=r.value, unit=r.unit)
        session.add(reading)
        created.append(reading)

    session.commit()
    for r in created:
        session.refresh(r)

    return {"count": len(created), "readings": created}


@app.delete("/sensors/{sensor_id}", status_code=204)
def delete_sensor(
    sensor_id: int,
    x_api_key: str = Header(..., description="Sensor API key"),
    session: Session = Depends(get_session),
):
    """Delete a sensor and all its readings."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")

    readings = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
    ).all()
    for r in readings:
        session.delete(r)

    session.delete(sensor)
    session.commit()
