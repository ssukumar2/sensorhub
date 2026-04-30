"""Deep health check that verifies all backend dependencies."""
import socket
import logging
from pathlib import Path
from sqlmodel import Session, text
from app.database import engine

log = logging.getLogger("sensorhub.health")

def check_database() -> dict:
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {"database": "ok"}
    except Exception as e:
        log.error("database health check failed: %s", e)
        return {"database": "error", "detail": str(e)}

def check_mqtt(host: str = "localhost", port: int = 1883) -> dict:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.close()
        return {"mqtt": "ok"}
    except (socket.error, OSError) as e:
        return {"mqtt": "unreachable", "detail": str(e)}

def check_disk() -> dict:
    import shutil
    usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024 ** 3)
    status = "ok" if free_gb > 1.0 else "low"
    return {"disk": status, "free_gb": round(free_gb, 2)}

def full_health_check() -> dict:
    db = check_database()
    mqtt = check_mqtt()
    disk = check_disk()
    all_ok = all(v.get(k) == "ok" for d in [db, mqtt, disk] for k, v in [(list(d.keys())[0], d)])
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": {**db, **mqtt, **disk},
    }
