"""FastAPI dependencies for sensor authentication."""
import secrets
from fastapi import Header, HTTPException, Request, Depends
from sqlmodel import Session
from app.database import get_session
from app.models import Sensor
from app.security.hmac_verify import verify_hmac


async def require_signed_sensor(
    request: Request,
    x_api_key: str = Header(..., description="Sensor API key"),
    x_nonce: str = Header(..., description="Unique request nonce"),
    x_timestamp: str = Header(..., description="Unix timestamp"),
    x_signature: str = Header(..., description="HMAC-SHA256 signature"),
    session: Session = Depends(get_session),
) -> Sensor:
    """Authenticate sensor via API key + HMAC over raw body."""
    body = (await request.body()).decode("utf-8")
    sensors = session.query(Sensor).all()
    for s in sensors:
        if secrets.compare_digest(s.api_key, x_api_key):
            if not verify_hmac(s.api_key, body, x_nonce, x_timestamp, x_signature):
                raise HTTPException(status_code=401, detail="invalid signature")
            return s
    raise HTTPException(status_code=401, detail="invalid api key")
