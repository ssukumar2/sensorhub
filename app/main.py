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
from app.can.buffer import buffer as can_buffer
from app.net.udp_receiver import stats as udp_stats
from app.notes import registry as notes_registry

FIRMWARE_DIR = os.environ.get("FIRMWARE_DIR", "/tmp/sensorhub_firmware")
os.makedirs(FIRMWARE_DIR, exist_ok=True)
from app.middleware import RateLimiter

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import time as _time

_start_time = _time.time()
_request_count = 0
_last_seen: dict = {}

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
    can = can_buffer.stats()
    return {
        "sensors": sensor_count,
        "readings": reading_count,
        "groups": len(groups),
        "group_names": list(groups.keys()),
        "active_alerts": len(active),
        "firmware_latest": firmware_tracker.latest().get("version", ""),
        "can_frames_received": can["frames_received"],
        "can_errors": can["errors"],
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


@app.post("/sensors/{sensor_id}/disable")
def disable_sensor(
    sensor_id: int,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Mark a sensor inactive via state=disabled tag."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    tag_registry.add_tag(sensor_id, "state", "disabled")
    audit_log.record("sensor.disable", f"sensor:{sensor_id}", {})
    return {"sensor_id": sensor_id, "state": "disabled"}


@app.post("/sensors/{sensor_id}/enable")
def enable_sensor(
    sensor_id: int,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Mark a sensor active again."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    tag_registry.add_tag(sensor_id, "state", "enabled")
    audit_log.record("sensor.enable", f"sensor:{sensor_id}", {})
    return {"sensor_id": sensor_id, "state": "enabled"}


@app.get("/audit/search")
def search_audit(action: Optional[str] = None, target: Optional[str] = None, limit: int = 100):
    """Filter audit log by action prefix or target."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    out = audit_log.recent(1000)
    if action:
        out = [e for e in out if e["action"].startswith(action)]
    if target:
        out = [e for e in out if target in e["target"]]
    return out[:limit]


@app.get("/sensors/{sensor_id}/tags/dict")
def sensor_tags_dict(sensor_id: int, session: Session = Depends(get_session)):
    """Return tags as a flat key->value dict (convenient for frontends)."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    return {t.key: t.value for t in tag_registry.get_tags(sensor_id)}


@app.get("/firmware/check-all")
def firmware_check_all():
    """Admin: list devices and whether each is on the latest firmware."""
    latest = firmware_tracker.latest()
    if not latest["version"]:
        return {"latest": None, "devices": []}
    out = []
    for fw in firmware_tracker.get_all():
        out.append({
            "sensor_id": fw.sensor_id,
            "version": fw.version,
            "up_to_date": fw.version == latest["version"],
        })
    return {"latest": latest["version"], "devices": out}


@app.get("/sensors/inactive")
def find_inactive_sensors(minutes: int = 10, session: Session = Depends(get_session)):
    """List sensors whose last reading is older than `minutes` (or never reported)."""
    if minutes < 1 or minutes > 10080:
        raise HTTPException(status_code=400, detail="minutes must be between 1 and 10080")
    from datetime import datetime as _dt, timedelta
    cutoff = _dt.utcnow() - timedelta(minutes=minutes)
    sensors = session.exec(select(Sensor)).all()
    out = []
    for sensor in sensors:
        last = session.exec(
            select(Reading).where(Reading.sensor_id == sensor.id)
            .order_by(Reading.id.desc()).limit(1)
        ).first()
        if last is None:
            out.append({"sensor_id": sensor.id, "name": sensor.name, "last_seen": None})
        elif last.recorded_at and last.recorded_at < cutoff:
            out.append({
                "sensor_id": sensor.id,
                "name": sensor.name,
                "last_seen": last.recorded_at.isoformat(),
            })
    return out


@app.get("/groups/{name}/stats")
def group_stats(name: str, session: Session = Depends(get_session)):
    """Aggregate readings across all sensors in a group."""
    groups = tag_registry.get_groups()
    if name not in groups:
        raise HTTPException(status_code=404, detail=f"group '{name}' not found")
    sensor_ids = groups[name]
    rows = session.exec(select(Reading).where(Reading.sensor_id.in_(sensor_ids))).all()
    if not rows:
        return {"group": name, "sensor_count": len(sensor_ids), "reading_count": 0, "avg": None, "min": None, "max": None}
    values = [r.value for r in rows]
    return {
        "group": name,
        "sensor_count": len(sensor_ids),
        "reading_count": len(values),
        "avg": round(sum(values)/len(values), 4),
        "min": min(values),
        "max": max(values),
    }


@app.get("/sensors/duplicates")
def find_duplicate_sensors(session: Session = Depends(get_session)):
    """Find sensors with identical names (potential data hygiene issue)."""
    sensors = session.exec(select(Sensor)).all()
    by_name = {}
    for s in sensors:
        by_name.setdefault(s.name, []).append({"id": s.id, "location": s.location})
    return {name: ids for name, ids in by_name.items() if len(ids) > 1}


@app.get("/can/stats")
def can_stats():
    """CAN receiver stats: frames received, errors, per-sensor breakdown."""
    return can_buffer.stats()


@app.get("/can/frames/recent")
def can_frames_recent(limit: int = 50):
    """Recent CAN frames seen by the gateway."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return can_buffer.recent(limit)


@app.get("/can/frames/by-sensor/{sensor_id}")
def can_frames_by_sensor(sensor_id: int, limit: int = 50):
    """Recent CAN frames received for a specific sensor."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    all_frames = can_buffer.recent(500)
    out = [f for f in all_frames if f["sensor_id"] == sensor_id][:limit]
    return out


@app.delete("/can/reset", status_code=204)
def can_reset():
    """Admin: clear the CAN frame buffer and stats counters."""
    can_buffer.reset()
    audit_log.record("can.reset", "buffer", {})
    return None


@app.get("/readings/since/{last_id}")
def readings_since(last_id: int, limit: int = 100, session: Session = Depends(get_session)):
    """Return readings with id > last_id, oldest first."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    rows = session.exec(
        select(Reading).where(Reading.id > last_id).order_by(Reading.id).limit(limit)
    ).all()
    return rows


@app.get("/sensors/{sensor_id}/value/last")
def last_value(sensor_id: int, session: Session = Depends(get_session)):
    """Return only the last value and unit for a sensor (compact)."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    row = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(1)
    ).first()
    if row is None:
        return {"sensor_id": sensor_id, "value": None, "unit": None}
    return {"sensor_id": sensor_id, "value": row.value, "unit": row.unit}


@app.get("/sensors/{sensor_id}/rate")
def sensor_rate(sensor_id: int, minutes: int = 5, session: Session = Depends(get_session)):
    """Return readings-per-minute for a sensor over last N minutes."""
    if minutes < 1 or minutes > 1440:
        raise HTTPException(status_code=400, detail="minutes must be between 1 and 1440")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    from datetime import datetime as _dt, timedelta
    cutoff = _dt.utcnow() - timedelta(minutes=minutes)
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .where(Reading.recorded_at >= cutoff)
    ).all()
    count = len(rows)
    return {
        "sensor_id": sensor_id,
        "count": count,
        "window_minutes": minutes,
        "rate_per_minute": round(count / minutes, 3),
    }


@app.get("/sensors/{sensor_id}/stuck")
def detect_stuck_sensor(sensor_id: int, samples: int = 10, session: Session = Depends(get_session)):
    """Check if the last N readings are all identical (suspected stuck sensor)."""
    if samples < 2 or samples > 100:
        raise HTTPException(status_code=400, detail="samples must be between 2 and 100")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(samples)
    ).all()
    if len(rows) < samples:
        return {"sensor_id": sensor_id, "stuck": False, "samples": len(rows), "reason": "not enough data"}
    values = {r.value for r in rows}
    return {
        "sensor_id": sensor_id,
        "stuck": len(values) == 1,
        "samples": samples,
        "unique_values": len(values),
    }


@app.get("/sensors/{sensor_id}/anomalies")
def sensor_anomalies(sensor_id: int, window: int = 100, sigma: float = 3.0,
                      session: Session = Depends(get_session)):
    """Find readings more than `sigma` standard deviations from window mean."""
    if window < 10 or window > 5000:
        raise HTTPException(status_code=400, detail="window must be between 10 and 5000")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(window)
    ).all()
    if len(rows) < 10:
        return {"sensor_id": sensor_id, "anomalies": [], "window": len(rows), "reason": "not enough data"}
    values = [r.value for r in rows]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    stddev = variance ** 0.5
    threshold = sigma * stddev
    anomalies = [
        {"id": r.id, "value": r.value, "deviation": round(abs(r.value - mean), 4)}
        for r in rows if abs(r.value - mean) > threshold
    ]
    return {
        "sensor_id": sensor_id,
        "window": len(rows),
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "sigma": sigma,
        "anomalies": anomalies,
    }


@app.get("/fleet/health")
def fleet_health(session: Session = Depends(get_session)):
    """High-level fleet health score and breakdown."""
    from datetime import datetime as _dt, timedelta
    cutoff = _dt.utcnow() - timedelta(minutes=10)
    sensors = session.exec(select(Sensor)).all()
    total = len(sensors)
    if total == 0:
        return {"total": 0, "active_pct": 0, "fw_uptodate_pct": 0, "status": "empty"}
    active = 0
    for s in sensors:
        last = session.exec(
            select(Reading).where(Reading.sensor_id == s.id)
            .order_by(Reading.id.desc()).limit(1)
        ).first()
        if last and last.recorded_at and last.recorded_at >= cutoff:
            active += 1
    latest_fw = firmware_tracker.latest().get("version", "")
    uptodate = sum(1 for fw in firmware_tracker.get_all() if fw.version == latest_fw) if latest_fw else 0
    fw_pct = (uptodate / total) * 100 if latest_fw else 0
    active_pct = (active / total) * 100
    if active_pct >= 90 and fw_pct >= 80:
        status = "healthy"
    elif active_pct >= 50:
        status = "degraded"
    else:
        status = "unhealthy"
    return {
        "total": total,
        "active_count": active,
        "active_pct": round(active_pct, 1),
        "fw_uptodate_count": uptodate,
        "fw_uptodate_pct": round(fw_pct, 1),
        "status": status,
    }


@app.get("/sensors/{sensor_id}/export.csv")
def export_readings_csv(sensor_id: int, limit: int = 1000, session: Session = Depends(get_session)):
    """Stream readings as CSV for download."""
    if limit < 1 or limit > 100000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100000")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id).limit(limit)
    ).all()
    from io import StringIO
    buf = StringIO()
    buf.write("id,sensor_id,value,unit,recorded_at\n")
    for r in rows:
        ts = r.recorded_at.isoformat() if r.recorded_at else ""
        buf.write(f"{r.id},{r.sensor_id},{r.value},{r.unit},{ts}\n")
    from fastapi.responses import Response
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sensor-{sensor_id}.csv"'},
    )


@app.get("/readings/export.csv")
def export_all_readings_csv(
    sensor_id: Optional[int] = None,
    limit: int = 10000,
    session: Session = Depends(get_session),
):
    """Export readings as CSV. Optionally filter by sensor_id."""
    if limit < 1 or limit > 100000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100000")
    statement = select(Reading, Sensor).join(Sensor, Sensor.id == Reading.sensor_id)
    if sensor_id is not None:
        statement = statement.where(Reading.sensor_id == sensor_id)
    statement = statement.order_by(Reading.id).limit(limit)
    rows = session.exec(statement).all()
    from io import StringIO
    buf = StringIO()
    buf.write("id,sensor_id,sensor_name,value,unit,recorded_at\n")
    for r, sensor in rows:
        ts = r.recorded_at.isoformat() if r.recorded_at else ""
        buf.write(f"{r.id},{r.sensor_id},{sensor.name},{r.value},{r.unit},{ts}\n")
    from fastapi.responses import Response
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="readings.csv"'},
    )


@app.post("/commands/{cmd_id}/cancel")
def cancel_command(cmd_id: str):
    """Cancel a pending command before delivery."""
    if not command_queue.cancel(cmd_id):
        cmd = command_queue.get(cmd_id)
        if cmd is None:
            raise HTTPException(status_code=404, detail="command not found")
        raise HTTPException(status_code=409, detail=f"cannot cancel command in status: {cmd.status}")
    audit_log.record("command.cancel", cmd_id, {})
    return {"id": cmd_id, "status": "cancelled"}


@app.get("/sensors/{sensor_id}/percentiles")
def sensor_percentiles(sensor_id: int, window: int = 100, session: Session = Depends(get_session)):
    """Return p50/p90/p95/p99 of last N readings."""
    if window < 4 or window > 5000:
        raise HTTPException(status_code=400, detail="window must be between 4 and 5000")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(window)
    ).all()
    if not rows:
        return {"sensor_id": sensor_id, "count": 0, "p50": None, "p90": None, "p95": None, "p99": None}
    values = sorted(r.value for r in rows)
    n = len(values)
    def pct(p):
        idx = min(n - 1, int(round((p / 100.0) * (n - 1))))
        return round(values[idx], 4)
    return {
        "sensor_id": sensor_id, "count": n,
        "p50": pct(50), "p90": pct(90), "p95": pct(95), "p99": pct(99),
    }


@app.get("/sensors/{sensor_id}/trend")
def sensor_trend(sensor_id: int, window: int = 50, session: Session = Depends(get_session)):
    """Linear regression slope of last N readings: positive = rising, negative = falling."""
    if window < 3 or window > 5000:
        raise HTTPException(status_code=400, detail="window must be between 3 and 5000")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(window)
    ).all()
    rows = list(reversed(rows))
    if len(rows) < 3:
        return {"sensor_id": sensor_id, "count": len(rows), "slope": None, "direction": "unknown"}
    n = len(rows)
    xs = list(range(n))
    ys = [r.value for r in rows]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    slope = num / den if den else 0
    if slope > 0.01:
        direction = "rising"
    elif slope < -0.01:
        direction = "falling"
    else:
        direction = "flat"
    return {"sensor_id": sensor_id, "count": n, "slope": round(slope, 4), "direction": direction}


@app.get("/sensors/{sensor_id}/threshold-violations")
def threshold_violations(
    sensor_id: int,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    window: int = 1000,
    session: Session = Depends(get_session),
):
    """Count and return readings outside provided bounds in last N readings."""
    if window < 1 or window > 10000:
        raise HTTPException(status_code=400, detail="window must be between 1 and 10000")
    if min_value is None and max_value is None:
        raise HTTPException(status_code=400, detail="provide min_value and/or max_value")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(window)
    ).all()
    violations = []
    for r in rows:
        kind = None
        if min_value is not None and r.value < min_value:
            kind = "below"
        elif max_value is not None and r.value > max_value:
            kind = "above"
        if kind:
            violations.append({"id": r.id, "value": r.value, "kind": kind})
    return {
        "sensor_id": sensor_id, "checked": len(rows),
        "violations": len(violations), "items": violations[:50],
    }


@app.post("/sensors/{sensor_id}/notes")
def add_sensor_note(
    sensor_id: int,
    text: str,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Attach a freeform note to a sensor."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    if not text or len(text) > 1000:
        raise HTTPException(status_code=400, detail="text required, max 1000 chars")
    notes_registry.add(sensor_id, text)
    return {"sensor_id": sensor_id, "notes": notes_registry.list_for(sensor_id)}


@app.get("/sensors/{sensor_id}/notes")
def list_sensor_notes(sensor_id: int, session: Session = Depends(get_session)):
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    return notes_registry.list_for(sensor_id)


@app.get("/readings/distribution/{sensor_id}")
def readings_distribution(
    sensor_id: int,
    bins: int = 10,
    window: int = 500,
    session: Session = Depends(get_session),
):
    """Histogram of last N readings split into `bins` buckets."""
    if bins < 2 or bins > 100:
        raise HTTPException(status_code=400, detail="bins must be between 2 and 100")
    if window < bins or window > 10000:
        raise HTTPException(status_code=400, detail="window must be >= bins and <= 10000")
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    rows = session.exec(
        select(Reading).where(Reading.sensor_id == sensor_id)
        .order_by(Reading.id.desc()).limit(window)
    ).all()
    if not rows:
        return {"sensor_id": sensor_id, "count": 0, "buckets": []}
    values = [r.value for r in rows]
    lo, hi = min(values), max(values)
    if lo == hi:
        return {"sensor_id": sensor_id, "count": len(values), "buckets": [{"from": lo, "to": hi, "count": len(values)}]}
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    buckets = [
        {"from": round(lo + i * width, 4), "to": round(lo + (i + 1) * width, 4), "count": counts[i]}
        for i in range(bins)
    ]
    return {"sensor_id": sensor_id, "count": len(values), "buckets": buckets}


@app.post("/sensors/{sensor_id}/copy", status_code=201)
def copy_sensor(
    sensor_id: int,
    new_name: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Duplicate a sensor: same location and tags, new api key, new id."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    name = new_name or (sensor.name + "-copy")
    new_sensor = Sensor(name=name, location=sensor.location)
    session.add(new_sensor)
    session.commit()
    session.refresh(new_sensor)
    for tag in tag_registry.get_tags(sensor_id):
        tag_registry.add_tag(new_sensor.id, tag.key, tag.value)
    audit_log.record("sensor.copy", f"from:{sensor_id} to:{new_sensor.id}", {})
    return new_sensor


@app.post("/sensors/{sensor_id}/keep-alive")
def keep_alive(
    sensor_id: int,
    x_api_key: str = Header(...),
    session: Session = Depends(get_session),
):
    """Device heartbeat. Records last-seen without inserting a reading."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    if not secrets.compare_digest(sensor.api_key, x_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")
    from datetime import datetime as _dt
    _last_seen[sensor_id] = _dt.utcnow()
    return {"sensor_id": sensor_id, "last_seen": _last_seen[sensor_id].isoformat()}


@app.get("/sensors/{sensor_id}/last-seen")
def get_last_seen(sensor_id: int, session: Session = Depends(get_session)):
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    ts = _last_seen.get(sensor_id)
    return {"sensor_id": sensor_id, "last_seen": ts.isoformat() if ts else None}


@app.post("/sensors/{sensor_id}/restart")
def restart_sensor(sensor_id: int, session: Session = Depends(get_session)):
    """Admin convenience: enqueue a 'restart' command for a device."""
    sensor = session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")
    cmd = command_queue.enqueue(sensor_id, "restart", {})
    audit_log.record("sensor.restart", f"sensor:{sensor_id}", {"command_id": cmd.id})
    return {"sensor_id": sensor_id, "command_id": cmd.id, "type": "restart"}


@app.get("/udp/stats")
def get_udp_stats():
    """UDP receiver stats: packets, errors, bytes, last-seen, per-sensor counts."""
    return udp_stats.snapshot()


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
    state_tags = [t for t in tag_registry.get_tags(payload.sensor_id) if t.key == "state"]
    if state_tags and state_tags[0].value == "disabled":
        raise HTTPException(status_code=403, detail="sensor is disabled")
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