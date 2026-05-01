"""Automatic data retention and old reading cleanup."""
import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select, col
from app.database import engine
from app.models import Reading

log = logging.getLogger("sensorhub.retention")

def cleanup_old_readings(max_age_days: int = 90, batch_size: int = 1000) -> int:
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    total_deleted = 0

    with Session(engine) as session:
        while True:
            old = session.exec(
                select(Reading)
                .where(Reading.timestamp < cutoff)
                .limit(batch_size)
            ).all()

            if not old:
                break

            for r in old:
                session.delete(r)
            session.commit()
            total_deleted += len(old)
            log.info("deleted %d old readings (total: %d)", len(old), total_deleted)

    log.info("retention cleanup complete: %d readings removed", total_deleted)
    return total_deleted

def get_storage_stats() -> dict:
    with Session(engine) as session:
        readings = session.exec(select(Reading)).all()
        if not readings:
            return {"count": 0, "oldest": None, "newest": None}
        timestamps = [r.timestamp for r in readings if hasattr(r, 'timestamp') and r.timestamp]
        return {
            "count": len(readings),
            "oldest": str(min(timestamps)) if timestamps else None,
            "newest": str(max(timestamps)) if timestamps else None,
        }
