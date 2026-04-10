"""
beaconnet — secure sensor network gateway.

Day 1: basic REST API to register sensors and submit/query readings.
Persistence is SQLite via SQLModel. No authentication yet — that comes next.
"""
from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import (
    Sensor,
    Reading,
    SensorCreate,
    ReadingCreate,
)


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


# -------- Health check --------

@app.get("/health")
def health():
    """Simple liveness probe. Useful for Docker/Kubernetes later."""
    return {"status": "ok", "service": "beaconnet", "version": "0.1.0"}


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
    session: Session = Depends(get_session),
):
    """Submit a telemetry reading from a sensor."""
    # Check the sensor exists before inserting the reading.
    sensor = session.get(Sensor, payload.sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")

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