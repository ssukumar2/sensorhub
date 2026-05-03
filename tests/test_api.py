"""Tests for the sensorhub REST API."""
import json
import time
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app
from app.security import (
    generate_api_key,
    constant_time_compare,
    compute_hmac,
    verify_hmac,
    is_timestamp_fresh,
    generate_nonce,
    compute_hmac_signed,
)

init_db()
#client = TestClient(app)
client = TestClient(app, raise_server_exceptions=True)


def _signed_post(path, body_obj, api_key):
    """POST signed per app.security.hmac_verify contract."""
    body = json.dumps(body_obj, separators=(",", ":"))
    nonce = generate_nonce()
    timestamp = str(int(time.time()))
    signature = compute_hmac_signed(api_key, body, nonce, timestamp)
    return client.post(
        path,
        content=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "x-nonce": nonce,
            "x-timestamp": timestamp,
            "x-signature": signature,
        },
    )


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "sensorhub"


def test_register_sensor_returns_api_key():
    response = client.post(
        "/sensors",
        json={"name": "test-sensor", "location": "testlab"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert "api_key" in body
    assert len(body["api_key"]) > 20


def test_list_sensors_works():
    response = client.get("/sensors")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_submit_reading_requires_api_key():
    reg = client.post(
        "/sensors",
        json={"name": "test-auth-sensor", "location": "lab"},
    ).json()
    response = client.post(
        "/readings",
        json={"sensor_id": reg["id"], "value": 22.0, "unit": "celsius"},
    )
    assert response.status_code == 422


def test_submit_reading_with_valid_key():
    reg = client.post(
        "/sensors",
        json={"name": "test-valid-sensor", "location": "lab"},
    ).json()
    response = _signed_post(
        "/readings",
        {"sensor_id": reg["id"], "value": 22.5, "unit": "celsius"},
        reg["api_key"],
    )
    assert response.status_code == 201


def test_submit_reading_with_wrong_key():
    reg = client.post(
        "/sensors",
        json={"name": "test-wrong-key-sensor", "location": "lab"},
    ).json()
    response = _signed_post(
        "/readings",
        {"sensor_id": reg["id"], "value": 22.5, "unit": "celsius"},
        "wrong-key-12345",
    )
    assert response.status_code == 401


def test_metrics_returns_uptime():
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "uptime_seconds" in body
    assert "request_count" in body
    assert body["service"] == "sensorhub"


def test_api_key_generation():
    key = generate_api_key()
    assert len(key) > 20
    assert key != generate_api_key()


def test_constant_time_compare():
    assert constant_time_compare("abc", "abc") is True
    assert constant_time_compare("abc", "xyz") is False


def test_hmac_sign_and_verify():
    key = "mysecret"
    msg = "hello world"
    sig = compute_hmac(key, msg)
    assert verify_hmac(key, msg, sig) is True
    assert verify_hmac(key, msg, "wrongsig") is False
    assert verify_hmac("wrongkey", msg, sig) is False


def test_timestamp_freshness():
    now = str(int(time.time()))
    assert is_timestamp_fresh(now) is True
    old = str(int(time.time()) - 60)
    assert is_timestamp_fresh(old) is False
    assert is_timestamp_fresh("notanumber") is False


def test_nonce_generation():
    n1 = generate_nonce()
    n2 = generate_nonce()
    assert len(n1) == 32
    assert n1 != n2


def test_rate_limiter_allows_normal_requests():
    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200


def test_batch_reading_submission():
    reg = client.post("/sensors", json={"name": "batch-sensor", "location": "lab"}).json()
    readings = [
        {"sensor_id": reg["id"], "value": 22.0, "unit": "celsius"},
        {"sensor_id": reg["id"], "value": 23.5, "unit": "celsius"},
        {"sensor_id": reg["id"], "value": 21.0, "unit": "celsius"},
    ]
    response = _signed_post("/readings/batch", readings, reg["api_key"])
    assert response.status_code == 201
    assert response.json()["count"] == 3


def test_delete_sensor():
    reg = client.post(
        "/sensors",
        json={"name": "delete-me", "location": "lab"},
    ).json()
    response = client.delete(
        f"/sensors/{reg['id']}",
        headers={"x-api-key": reg["api_key"]},
    )
    assert response.status_code == 204
    assert client.get(f"/sensors/{reg['id']}").status_code == 404


def test_update_sensor():
    reg = client.post(
        "/sensors",
        json={"name": "old-name", "location": "old-loc"},
    ).json()
    response = client.patch(
        f"/sensors/{reg['id']}?name=new-name&location=new-loc",
        headers={"x-api-key": reg["api_key"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "new-name"
    assert body["location"] == "new-loc"


def test_system_status():
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sensorhub"
    assert "sensors" in body
    assert "readings" in body


def test_version_endpoint():
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert "api_version" in body
    assert "http" in body["protocols"]

def test_submit_reading_with_bad_signature():
    reg = client.post(
        "/sensors",
        json={"name": "test-bad-sig-sensor", "location": "lab"},
    ).json()
    body = json.dumps({"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, separators=(",", ":"))
    nonce = generate_nonce()
    timestamp = str(int(time.time()))
    response = client.post(
        "/readings",
        content=body,
        headers={
            "content-type": "application/json",
            "x-api-key": reg["api_key"],
            "x-nonce": nonce,
            "x-timestamp": timestamp,
            "x-signature": "deadbeef" * 8,
        },
    )
    assert response.status_code == 401


def test_submit_reading_with_stale_timestamp():
    reg = client.post(
        "/sensors",
        json={"name": "test-stale-sensor", "location": "lab"},
    ).json()
    body = json.dumps({"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, separators=(",", ":"))
    nonce = generate_nonce()
    stale = str(int(time.time()) - 120)
    signature = compute_hmac_signed(reg["api_key"], body, nonce, stale)
    response = client.post(
        "/readings",
        content=body,
        headers={
            "content-type": "application/json",
            "x-api-key": reg["api_key"],
            "x-nonce": nonce,
            "x-timestamp": stale,
            "x-signature": signature,
        },
    )
    assert response.status_code == 401