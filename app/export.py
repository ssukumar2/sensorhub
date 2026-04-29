"""Export sensor readings as CSV or JSON for download."""
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from app.database import get_session
from app.models import Reading

router = APIRouter()

@router.get("/export/readings")
def export_readings(
    format: str = Query("csv", regex="^(csv|json)$"),
    sensor_id: int = None,
    session: Session = Depends(get_session),
):
    query = select(Reading)
    if sensor_id is not None:
        query = query.where(Reading.sensor_id == sensor_id)
    readings = session.exec(query).all()

    if format == "json":
        data = [{"id": r.id, "sensor_id": r.sensor_id, "value": r.value,
                 "unit": r.unit} for r in readings]
        return data

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "sensor_id", "value", "unit"])
    for r in readings:
        writer.writerow([r.id, r.sensor_id, r.value, r.unit])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=readings.csv"},
    )
