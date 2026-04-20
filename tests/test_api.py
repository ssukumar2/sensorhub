"""Tests for the sensorhub REST API."""
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
)
import time


# Create tables before any tests run
init_db()

client = TestClient(app)

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
    # First register a sensor
    reg = client.post(
        "/sensors",
        json={"name": "test-auth-sensor", "location": "lab"},
    ).json()

    # Try without api key -> should fail
    response = client.post(
        "/readings",
        json={"sensor_id": reg["id"], "value": 22.0, "unit": "celsius"},
    )
    assert response.status_code == 422  # missing required header


def test_submit_reading_with_valid_key():
    reg = client.post(
        "/sensors",
        json={"name": "test-valid-sensor", "location": "lab"},
    ).json()

    response = client.post(
        "/readings",
        json={"sensor_id": reg["id"], "value": 22.5, "unit": "celsius"},
        headers={"x-api-key": reg["api_key"]},
    )
    assert response.status_code == 201


def test_submit_reading_with_wrong_key():
    reg = client.post(
        "/sensors",
        json={"name": "test-wrong-key-sensor", "location": "lab"},
    ).json()

    response = client.post(
        "/readings",
        json={"sensor_id": reg["id"], "value": 22.5, "unit": "celsius"},
        headers={"x-api-key": "wrong-key-12345"},
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
    key2 = generate_api_key()
    assert key != key2


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