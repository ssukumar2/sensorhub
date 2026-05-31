"""
SensorHUb — secure sensor network gateway.

"""
import hashlib
import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import (
    Sensor,
    Reading,
    SensorCreate,
    ReadingCreate,
)
from app.security.dependencies import require_signed_sensor
from app.firmware import tracker as firmware_tracker
from app.tags import registry as tag_registry
from app.alerts import engine as alert_engine, AlertRule
from app.commands import queue as command_queue
from app.audit import log as audit_log

FIRMWARE_DIR = os.environ.get("FIRMWARE_DIR", "/tmp/sensorhub_firmware")
os.makedirs(FIRMWARE_DIR, exist_ok=True)
from app.middleware import RateLimiter

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def list_sensors(
    offset: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List sensors with offset/limit pagination."""
    if offset < 0 or limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="invalid pagination")
    return session.exec(select(Sensor).offset(offset).limit(limit)).all()


@app.get("/sensors/count")
def count_sensors(session: Session = Depends(get_session)):
    """Return total sensor count."""
    return {"count": len(session.exec(select(Sensor)).all())}


@app.get("/sensors/search")
def search_sensors(q: str, session: Session = Depends(get_session)):
    """Search sensors by name or location substring."""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="query must be at least 2 chars")
    rows = session.exec(select(Sensor)).all()
    ql = q.lower()
    return [s for s in rows if ql in s.name.lower() or ql in (s.location or "").lower()]


@app.get("/readings/by-unit/{unit}")
def readings_by_unit(unit: str, limit: int = 50, session: Session = Depends(get_session)):
    """Return recent readings filtered by unit."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    rows = session.exec(
        select(Reading).where(Reading.unit == unit).order_by(Reading.id.desc()).limit(limit)
    ).all()
    return rows


@app.get("/readings/count")
def count_readings(session: Session = Depends(get_session)):
    """Return total reading count across all sensors."""
    return {"count": len(session.exec(select(Reading)).all())}


@app.get("/sensors/by-location/{location}")
def sensors_by_location(location: str, session: Session = Depends(get_session)):
    """Return sensors at the given exact location."""
    rows = session.exec(select(Sensor).where(Sensor.location == location)).all()
    return rows


@app.get("/sensors/{sensor_id}/readings/count")
def count_sensor_readings(sensor_id: int, session: Session = Depends(get_session)):
    """Return reading count for a specific sensor."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(select(Reading).where(Reading.sensor_id == sensor_id)).all()
    return {"sensor_id": sensor_id, "count": len(rows)}


@app.get("/readings/units")
def list_units(session: Session = Depends(get_session)):
    """Return all distinct units currently in use."""
    rows = session.exec(select(Reading.unit)).all()
    return {"units": sorted(set(rows))}


@app.get("/sensors/{sensor_id}/readings/range")
def sensor_reading_range(sensor_id: int, session: Session = Depends(get_session)):
    """Return the time span of readings for a sensor."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id).order_by(Reading.recorded_at)
    ).all()
    if not rows:
        return {"sensor_id": sensor_id, "first": None, "last": None, "count": 0}
    return {
        "sensor_id": sensor_id,
        "first": rows[0].recorded_at.isoformat(),
        "last": rows[-1].recorded_at.isoformat(),
        "count": len(rows),
    }


@app.get("/firmware/latest")
def get_latest_firmware():
    """Return the latest available firmware version and download url."""
    return firmware_tracker.latest()


@app.post("/firmware/latest")
def set_latest_firmware(version: str, url: str = ""):
    """Admin: set the latest available firmware version."""
    if not version:
        raise HTTPException(status_code=400, detail="version required")
    firmware_tracker.set_latest(version, url)
    return firmware_tracker.latest()


@app.get("/firmware/versions")
def list_firmware_versions():
    """List all uploaded firmware binaries with size and sha."""
    out = []
    for fname in sorted(os.listdir(FIRMWARE_DIR)):
        if not fname.endswith(".bin"):
            continue
        version = fname[:-4]
        path = os.path.join(FIRMWARE_DIR, fname)
        sha_path = path + ".sha256"
        sha = ""
        if os.path.exists(sha_path):
            with open(sha_path) as f:
                sha = f.read().strip()
        out.append({"version": version, "size": os.path.getsize(path), "sha256": sha})
    return out


@app.delete("/firmware/{version}", status_code=204)
def delete_firmware_version(version: str):
    """Remove an uploaded firmware binary and its checksum."""
    path = os.path.join(FIRMWARE_DIR, f"{version}.bin")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="firmware not found")
    os.remove(path)
    sha_path = path + ".sha256"
    if os.path.exists(sha_path):
        os.remove(sha_path)
    return None


@app.post("/firmware/upload")
async def upload_firmware(version: str, request: Request):
    """Upload a firmware binary. Body is the raw file."""
    if not version:
        raise HTTPException(status_code=400, detail="version required")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty body")
    path = os.path.join(FIRMWARE_DIR, f"{version}.bin")
    with open(path, "wb") as f:
        f.write(body)
    sha = hashlib.sha256(body).hexdigest()
    with open(path + ".sha256", "w") as f:
        f.write(sha)
    firmware_tracker.set_latest(version, f"/firmware/download/{version}")
    audit_log.record("firmware.upload", f"version:{version}", {"size": len(body), "sha256": sha})
    return {"version": version, "size": len(body), "sha256": sha, "path": path}


@app.get("/firmware/download/{version}")
def download_firmware(version: str):
    """Stream a firmware binary back with x-sha256 integrity header."""
    from fastapi.responses import FileResponse
    path = os.path.join(FIRMWARE_DIR, f"{version}.bin")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="firmware not found")
    sha = ""
    sha_path = path + ".sha256"
    if os.path.exists(sha_path):
        with open(sha_path) as f:
            sha = f.read().strip()
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=f"firmware-{version}.bin",
        headers={"x-sha256": sha} if sha else None,
    )


@app.get("/firmware/check")
def check_firmware_update(current_version: str):
    """Device asks: am I up to date?"""
    latest = firmware_tracker.latest()
    if not latest["version"]:
        return {"update_available": False, "current": current_version, "latest": None}
    return {
        "update_available": current_version != latest["version"],
        "current": current_version,
        "latest": latest["version"],
        "url": latest["url"],
    }


@app.get("/firmware/latest")
def get_latest_firmware():
    """Return the latest available firmware version and download url."""
    return firmware_tracker.latest()


@app.post("/firmware/latest")
def set_latest_firmware(version: str, url: str = ""):
    """Admin: set the latest available firmware version."""
    if not version:
        raise HTTPException(status_code=400, detail="version required")
    firmware_tracker.set_latest(version, url)
    return firmware_tracker.latest()


@app.post("/firmware/report")
def report_firmware(
    sensor_id: int,
    version: str,
    build_date: str = "",
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Device reports its current firmware version."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    firmware_tracker.report(sensor_id, version, build_date)
    return {"sensor_id": sensor_id, "version": version, "status": "recorded"}


@app.get("/firmware/devices")
def list_firmware_devices():
    """Return firmware info for all reporting devices."""
    return [fw.__dict__ for fw in firmware_tracker.get_all()]


@app.get("/firmware/summary")
def firmware_summary():
    """Return aggregate firmware version counts."""
    return firmware_tracker.summary()


@app.post("/sensors/{sensor_id}/tags")
def add_sensor_tag(
    sensor_id: int,
    key: str,
    value: str,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Add or update a key/value tag on a sensor."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    if not key or not value:
        raise HTTPException(status_code=400, detail="key and value required")
    tag_registry.add_tag(sensor_id, key, value)
    return {"sensor_id": sensor_id, "tags": [{"key": t.key, "value": t.value} for t in tag_registry.get_tags(sensor_id)]}


@app.get("/sensors/{sensor_id}/tags")
def list_sensor_tags(sensor_id: int, session: Session = Depends(get_session)):
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    return [{"key": t.key, "value": t.value} for t in tag_registry.get_tags(sensor_id)]


@app.delete("/sensors/{sensor_id}/tags/{key}", status_code=204)
def remove_sensor_tag(
    sensor_id: int,
    key: str,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    tag_registry.remove_tag(sensor_id, key)
    return None


@app.get("/tags/search")
def search_by_tag(key: str, value: Optional[str] = None):
    """Find sensor ids that have a given tag (and optional value)."""
    if not key:
        raise HTTPException(status_code=400, detail="key required")
    return {"key": key, "value": value, "sensor_ids": tag_registry.find_by_tag(key, value)}


@app.get("/groups")
def list_groups():
    """List all fleet groups (sensors tagged with key='group')."""
    return tag_registry.get_groups()


@app.post("/alerts/rules")
def add_alert_rule(
    sensor_id: int,
    metric: str = "value",
    threshold_high: Optional[float] = None,
    threshold_low: Optional[float] = None,
    session: Session = Depends(get_session),
):
    """Configure a threshold rule for a sensor (admin)."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if threshold_high is None and threshold_low is None:
        raise HTTPException(status_code=400, detail="at least one threshold required")
    rule = AlertRule(sensor_id=sensor_id, metric=metric,
                     threshold_high=threshold_high, threshold_low=threshold_low)
    audit_log.record("alert.rule.add", f"sensor:{sensor_id}", {"high": threshold_high, "low": threshold_low})
    alert_engine.add_rule(rule)
    return {"sensor_id": sensor_id, "high": threshold_high, "low": threshold_low}


@app.get("/alerts/history")
def get_alert_history(limit: int = 50):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return alert_engine.get_history(limit)


@app.post("/sensors/{sensor_id}/commands")
def enqueue_command(
    sensor_id: int,
    type: str,
    payload: Optional[dict] = None,
    session: Session = Depends(get_session),
):
    """Hub admin queues a command for a device (e.g. reboot, set-interval, ota)."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not type:
        raise HTTPException(status_code=400, detail="command type required")
    audit_log.record("command.enqueue", f"sensor:{sensor_id}", {"type": type, "payload": payload})
    cmd = command_queue.enqueue(sensor_id, type, payload or {})
    return {"id": cmd.id, "type": cmd.type, "status": cmd.status}


@app.get("/sensors/{sensor_id}/commands/pending")
def poll_commands(
    sensor_id: int,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Device polls for pending commands. Auto-marks them delivered."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    pending = command_queue.pending_for(sensor_id)
    out = []
    for c in pending:
        out.append({"id": c.id, "type": c.type, "payload": c.payload})
        command_queue.mark_delivered(c.id)
    return out


@app.post("/commands/{cmd_id}/ack")
def ack_command(
    cmd_id: str,
    result: str = "",
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Device acks a command with optional result string."""
    cmd = command_queue.get(cmd_id)
    if cmd is None:
        raise HTTPException(status_code=404, detail="command not found")
    sensor = session.get(Sensor, cmd.sensor_id)
    if sensor is None or not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    command_queue.ack(cmd_id, result)
    return {"id": cmd_id, "status": "acked"}


@app.get("/sensors/{sensor_id}/commands/history")
def command_history(sensor_id: int, session: Session = Depends(get_session)):
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    cmds = command_queue.all_for(sensor_id)
    return [
        {"id": c.id, "type": c.type, "status": c.status, "payload": c.payload,
         "created_at": c.created_at.isoformat(),
         "delivered_at": c.delivered_at.isoformat() if c.delivered_at else None,
         "acked_at": c.acked_at.isoformat() if c.acked_at else None,
         "result": c.result}
        for c in cmds
    ]


@app.get("/audit/recent")
def get_audit_log(limit: int = 50):
    """Recent audit log entries, newest first."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return audit_log.recent(limit)


@app.post("/firmware/rollout")
def firmware_rollout(group: str, version: str):
    """Enqueue an ota-update command to every sensor tagged group=<name>."""
    if not group or not version:
        raise HTTPException(status_code=400, detail="group and version required")
    groups = tag_registry.get_groups()
    if group not in groups:
        raise HTTPException(status_code=404, detail=f"group '{group}' not found")
    targets = groups[group]
    out = []
    for sid in targets:
        cmd = command_queue.enqueue(sid, "ota-update", {"version": version})
        out.append({"sensor_id": sid, "command_id": cmd.id})
    audit_log.record("firmware.rollout", f"group:{group}", {"version": version, "count": len(out)})
    return {"group": group, "version": version, "targets": out}


@app.get("/readings/stream")
async def stream_readings(session: Session = Depends(get_session)):
    """Server-sent events stream of new readings."""
    async def gen():
        last_id = 0
        rows = session.exec(select(Reading).order_by(Reading.id.desc()).limit(1)).all()
        if rows:
            last_id = rows[0].id
        while True:
            new_rows = session.exec(
                select(Reading, Sensor)
                .join(Sensor, Sensor.id == Reading.sensor_id)
                .where(Reading.id > last_id)
                .order_by(Reading.id)
            ).all()
            for r, sensor in new_rows:
                payload = {
                    "id": r.id, "sensor_id": r.sensor_id, "sensor_name": sensor.name,
                    "value": r.value, "unit": r.unit,
                    "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                }
                import json as _json
                yield f"data: {_json.dumps(payload)}\n\n"
                last_id = r.id
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/sensors/{sensor_id}/readings/window")
def readings_window(
    sensor_id: int,
    since: Optional[str] = None,
    limit: int = 1000,
    session: Session = Depends(get_session),
):
    """Return readings newer than ISO timestamp `since`."""
    from datetime import datetime as _dt
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
    statement = select(Reading).where(Reading.sensor_id == sensor_id)
    if since:
        try:
            cutoff = _dt.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid ISO timestamp")
        statement = statement.where(Reading.recorded_at > cutoff)
    statement = statement.order_by(Reading.recorded_at).limit(limit)
    return session.exec(statement).all()


@app.get("/alerts/active")
def get_active_alerts():
    """Alerts triggered in the last 5 minutes."""
    out = []
    for a in alert_engine.active():
        a2 = dict(a)
        if "timestamp" in a2 and hasattr(a2["timestamp"], "isoformat"):
            a2["timestamp"] = a2["timestamp"].isoformat()
        out.append(a2)
    return out


@app.get("/fleet/summary")
def fleet_summary(session: Session = Depends(get_session)):
    """Single-call dashboard summary."""
    sensor_count = len(session.exec(select(Sensor)).all())
    reading_count = len(session.exec(select(Reading)).all())
    groups = tag_registry.get_groups()
    active = alert_engine.active()
    return {
        "sensors": sensor_count,
        "readings": reading_count,
        "groups": len(groups),
        "group_names": list(groups.keys()),
        "active_alerts": len(active),
        "firmware_latest": firmware_tracker.latest().get("version", ""),
    }


@app.get("/sensors/{sensor_id}/aggregate")
def sensor_aggregate(
    sensor_id: int,
    window: int = 100,
    bucket: int = 10,
    session: Session = Depends(get_session),
):
    """Bucket the last `window` readings into `bucket`-sized chunks with avg/min/max."""
    if window < 1 or window > 5000:
        raise HTTPException(status_code=400, detail="window must be between 1 and 5000")
    if bucket < 1 or bucket > window:
        raise HTTPException(status_code=400, detail="bucket must be between 1 and window")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(window)
    ).all()
    rows = list(reversed(rows))
    out = []
    for i in range(0, len(rows), bucket):
        chunk = rows[i:i+bucket]
        values = [r.value for r in chunk]
        out.append({
            "count": len(values),
            "avg": round(sum(values)/len(values), 4),
            "min": min(values),
            "max": max(values),
            "from": chunk[0].recorded_at.isoformat() if chunk[0].recorded_at else None,
            "to": chunk[-1].recorded_at.isoformat() if chunk[-1].recorded_at else None,
        })
    return out


@app.delete("/alerts/clear", status_code=204)
def clear_alert_history():
    """Admin: wipe alert history."""
    alert_engine.history.clear()
    audit_log.record("alerts.clear", "history", {})
    return None


@app.get("/alerts/rules")
def list_alert_rules():
    """List currently configured alert rules."""
    return [
        {"index": i, "sensor_id": r.sensor_id, "metric": r.metric,
         "threshold_high": r.threshold_high, "threshold_low": r.threshold_low}
        for i, r in enumerate(alert_engine.rules)
    ]


@app.delete("/alerts/rules/{idx}", status_code=204)
def delete_alert_rule(idx: int):
    """Remove rule by index from list."""
    if idx < 0 or idx >= len(alert_engine.rules):
        raise HTTPException(status_code=404, detail="rule index out of range")
    removed = alert_engine.rules.pop(idx)
    audit_log.record("alert.rule.delete", f"sensor:{removed.sensor_id}", {"index": idx})
    return None


@app.get("/commands/pending/all")
def list_all_pending_commands():
    """Admin: every pending command across all sensors."""
    all_pending = []
    seen_sensors = set()
    for sid, cmds in command_queue._queue.items():
        for c in cmds:
            if c.status == "pending":
                all_pending.append({
                    "id": c.id, "sensor_id": sid, "type": c.type,
                    "created_at": c.created_at.isoformat(),
                })
                seen_sensors.add(sid)
    return {"count": len(all_pending), "sensors": list(seen_sensors), "commands": all_pending}


@app.post("/sensors/bulk", status_code=201)
def create_bulk_sensors(
    sensors: List[SensorCreate],
    session: Session = Depends(get_session),
):
    """Create multiple sensors in one call. Caps at 100."""
    if not sensors:
        raise HTTPException(status_code=400, detail="empty list")
    if len(sensors) > 100:
        raise HTTPException(status_code=400, detail="max 100 sensors per call")
    created = []
    for sc in sensors:
        s = Sensor(name=sc.name, location=sc.location)
        session.add(s)
        created.append(s)
    session.commit()
    for s in created:
        session.refresh(s)
    return {"count": len(created), "sensors": created}


@app.get("/health/detail")
def health_detail(session: Session = Depends(get_session)):
    """Extended health with db state and last activity."""
    import os as _os
    sensor_count = len(session.exec(select(Sensor)).all())
    reading_count = len(session.exec(select(Reading)).all())
    last = session.exec(select(Reading).order_by(Reading.id.desc()).limit(1)).all()
    last_reading_at = last[0].recorded_at.isoformat() if last else None
    db_size = 0
    for db_name in ("sensorhub.db", "data.db", "test.db"):
        if _os.path.exists(db_name):
            db_size = _os.path.getsize(db_name)
            break
    return {
        "status": "ok",
        "uptime_seconds": int(_time.time() - _start_time),
        "sensors": sensor_count,
        "readings": reading_count,
        "last_reading_at": last_reading_at,
        "db_size_bytes": db_size,
    }


@app.delete("/readings/cleanup")
def cleanup_old_readings(days: int = 30, session: Session = Depends(get_session)):
    """Admin: delete readings older than N days."""
    if days < 1 or days > 3650:
        raise HTTPException(status_code=400, detail="days must be between 1 and 3650")
    from datetime import datetime as _dt, timedelta
    cutoff = _dt.utcnow() - timedelta(days=days)
    rows = session.exec(select(Reading).where(Reading.recorded_at < cutoff)).all()
    deleted = len(rows)
    for r in rows:
        session.delete(r)
    session.commit()
    audit_log.record("readings.cleanup", "global", {"days": days, "deleted": deleted})
    return {"deleted": deleted, "older_than_days": days}


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
    sensor: Sensor = Depends(require_signed_sensor),
    session: Session = Depends(get_session),
):
    """Submit a telemetry reading from a sensor."""
    if sensor.id != payload.sensor_id:
        raise HTTPException(status_code=403, detail="sensor id mismatch")
    reading = Reading(
        sensor_id=payload.sensor_id,
        value=payload.value,
        unit=payload.unit,
    )
    session.add(reading)
    session.commit()
    session.refresh(reading)
    alert_engine.evaluate(payload.sensor_id, payload.value, payload.unit)
    return reading


@app.post("/readings/batch", status_code=201)
def submit_batch_readings(
    readings: List[ReadingCreate],
    sensor: Sensor = Depends(require_signed_sensor),
    session: Session = Depends(get_session),
):
    """Submit multiple readings in a single request."""
    if not readings:
        raise HTTPException(status_code=400, detail="empty batch")
    for r in readings:
        if r.sensor_id != sensor.id:
            raise HTTPException(status_code=403, detail="sensor id mismatch")
    created = []
    for r in readings:
        reading = Reading(sensor_id=r.sensor_id, value=r.value, unit=r.unit)
        session.add(reading)
        created.append(reading)
    session.commit()
    for r in created:
        session.refresh(r)
    return {"count": len(created), "readings": created}

# @app.post("/readings", response_model=Reading, status_code=201)
# def submit_reading(
#     payload: ReadingCreate,
#     #sensor: Sensor = Depends(require_sensor_key),
#     x_api_key: str = Header(..., description="Sensor API key"),
#     session: Session = Depends(get_session),
# ):
#     """Submit a telemetry reading from a sensor."""
#     # Check the sensor exists before inserting the reading.
#     #sensor = session.get(Sensor, payload.sensor_id)
#     #if sensor is None:
#       #  raise HTTPException(status_code=404, detail="sensor not found")

#     sensor = session.get(Sensor, payload.sensor_id)
#     if sensor is None:
#         raise HTTPException(status_code=404, detail="sensor not found")
#     if not secrets.compare_digest(sensor.api_key, x_api_key):
#         raise HTTPException(status_code=401, detail="invalid api key")

#     reading = Reading(
#         sensor_id=payload.sensor_id,
#         value=payload.value,
#         unit=payload.unit,
#     )
#     session.add(reading)
#     session.commit()
#     session.refresh(reading)
#     return reading


# @app.post("/readings/batch", status_code=201)
# def submit_batch_readings(
#     readings: List[ReadingCreate],
#     x_api_key: str = Header(...),
#     session: Session = Depends(get_session),
# ):
#     """Submit multiple readings in a single request."""
#     if not readings:
#         raise HTTPException(status_code=400, detail="empty batch")

#     sensor = session.get(Sensor, readings[0].sensor_id)
#     if sensor is None:
#         raise HTTPException(status_code=404, detail="sensor not found")
#     if not secrets.compare_digest(sensor.api_key, x_api_key):
#         raise HTTPException(status_code=401, detail="invalid api key")

#     created = []
#     for r in readings:
#         reading = Reading(sensor_id=r.sensor_id, value=r.value, unit=r.unit)
#         session.add(reading)
#         created.append(reading)

#     session.commit()
#     for r in created:
#         session.refresh(r)

#     return {"count": len(created), "readings": created}


@app.get("/readings/recent")
def list_recent_readings(
    limit: int = 50,
    session: Session = Depends(get_session),
):
    """Return the most recent readings across all sensors with sensor name."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    rows = session.exec(
        select(Reading, Sensor)
        .join(Sensor, Sensor.id == Reading.sensor_id)
        .order_by(Reading.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "sensor_id": r.sensor_id,
            "sensor_name": sensor.name,
            "value": r.value,
            "unit": r.unit,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r, sensor in rows
    ]


@app.get("/sensors/{sensor_id}/stats")
def sensor_stats(
    sensor_id: int,
    window: int = 100,
    session: Session = Depends(get_session),
):
    """Return min/max/avg/count over the most recent `window` readings."""
    if window < 1 or window > 10000:
        raise HTTPException(status_code=400, detail="window must be between 1 and 10000")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading)
        .where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc())
        .limit(window)
    ).all()
    if not rows:
        return {"sensor_id": sensor_id, "count": 0, "min": None, "max": None, "avg": None}
    values = [r.value for r in rows]
    return {
        "sensor_id": sensor_id,
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 4),
    }


@app.get("/sensors/{sensor_id}/latest")
def latest_reading(sensor_id: int, session: Session = Depends(get_session)):
    """Return the single most recent reading for a sensor, or 404 if none."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    row = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id).order_by(Reading.id.desc()).limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="no readings yet")
    return row




@app.delete("/sensors/{sensor_id}/readings", status_code=204)
def clear_sensor_readings(
    sensor_id: int,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Delete all readings for a sensor (sensor itself stays)."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    rows = session.exec(select(Reading).where(Reading.sensor_id == sensor_id)).all()
    for r in rows:
        session.delete(r)
    session.commit()
    return None




@app.get("/sensors/{sensor_id}/readings", response_model=List[Reading])
def list_readings_for_sensor(
    sensor_id: int,
    limit: int = 100,
    min_value: float = None,
    max_value: float = None,
    session: Session = Depends(get_session),
):
    """List recent readings for a sensor, most recent first."""
    if min_value is not None and max_value is not None and min_value > max_value:
        raise HTTPException(status_code=400, detail="min_value cannot exceed max_value")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")

    statement = select(Reading).where(Reading.sensor_id == sensor_id)
    if min_value is not None:
        statement = statement.where(Reading.value >= min_value)
    if max_value is not None:
        statement = statement.where(Reading.value <= max_value)
    statement = statement.order_by(Reading.recorded_at.desc()).limit(limit)
    return session.exec(statement).all()


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


@app.patch("/sensors/{sensor_id}")
def update_sensor(
    sensor_id: int,
    name: str = None,
    location: str = None,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Update sensor name or location."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")

    if name is not None:
        sensor.name = name
    if location is not None:
        sensor.location = location

    session.add(sensor)
    session.commit()
    session.refresh(sensor)
    return sensor

@app.get("/status")
def system_status(session: Session = Depends(get_session)):
    """Overall system status."""
    sensor_count = len(session.exec(select(Sensor)).all())
    reading_count = len(session.exec(select(Reading)).all())
    return {
        "service": "sensorhub",
        "sensors": sensor_count,
        "readings": reading_count,
        "transports": ["http", "mqtt", "can"],
    }


@app.get("/version")
def version():
    """API version and capabilities."""
    return {
        "service": "sensorhub",
        "api_version": "0.2.0",
        "protocols": ["http", "mqtt", "can"],
        "security": ["api_key", "hmac_sha256", "replay_protection"],
    }