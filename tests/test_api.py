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

def test_readings_recent_returns_list():
    reg = client.post("/sensors", json={"name": "recent-sensor", "location": "lab"}).json()
    for v in (1.1, 2.2, 3.3):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get("/readings/recent?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(r["sensor_name"] == "recent-sensor" for r in body)


def test_readings_recent_rejects_bad_limit():
    assert client.get("/readings/recent?limit=0").status_code == 400
    assert client.get("/readings/recent?limit=9999").status_code == 400


def test_sensor_stats_empty():
    reg = client.post("/sensors", json={"name": "stats-empty", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["min"] is None


def test_sensor_stats_with_readings():
    reg = client.post("/sensors", json={"name": "stats-filled", "location": "lab"}).json()
    for v in (10.0, 20.0, 30.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["min"] == 10.0
    assert body["max"] == 30.0
    assert body["avg"] == 20.0


def test_sensor_stats_unknown_sensor():
    assert client.get("/sensors/99999/stats").status_code == 404


def test_sensor_stats_bad_window():
    reg = client.post("/sensors", json={"name": "stats-badw", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/stats?window=0").status_code == 400
    assert client.get(f"/sensors/{reg['id']}/stats?window=999999").status_code == 400


def test_sensor_stats_empty():
    reg = client.post("/sensors", json={"name": "stats-empty", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["min"] is None


def test_sensor_stats_with_readings():
    reg = client.post("/sensors", json={"name": "stats-filled", "location": "lab"}).json()
    for v in (10.0, 20.0, 30.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["min"] == 10.0
    assert body["max"] == 30.0
    assert body["avg"] == 20.0


def test_sensor_stats_unknown_sensor():
    assert client.get("/sensors/99999/stats").status_code == 404


def test_sensor_stats_bad_window():
    reg = client.post("/sensors", json={"name": "stats-badw", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/stats?window=0").status_code == 400
    assert client.get(f"/sensors/{reg['id']}/stats?window=999999").status_code == 400


def test_latest_reading_404_when_no_readings():
    reg = client.post("/sensors", json={"name": "latest-empty", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/latest").status_code == 404


def test_latest_reading_returns_most_recent():
    reg = client.post("/sensors", json={"name": "latest-ok", "location": "lab"}).json()
    for v in (1.0, 2.0, 3.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/latest")
    assert response.status_code == 200
    assert response.json()["value"] == 3.0


def test_latest_reading_unknown_sensor():
    assert client.get("/sensors/99999/latest").status_code == 404


def test_sensors_count_returns_int():
    response = client.get("/sensors/count")
    assert response.status_code == 200
    assert isinstance(response.json()["count"], int)


def test_search_rejects_short_query():
    assert client.get("/sensors/search?q=a").status_code == 400


def test_search_finds_by_name():
    client.post("/sensors", json={"name": "needle-sensor-xyz", "location": "lab"}).json()
    response = client.get("/sensors/search?q=needle-sensor-xyz")
    assert response.status_code == 200
    assert any(s["name"] == "needle-sensor-xyz" for s in response.json())


def test_search_finds_by_location():
    client.post("/sensors", json={"name": "loc-test", "location": "rooftop-unique"}).json()
    response = client.get("/sensors/search?q=rooftop-unique")
    assert response.status_code == 200
    assert any(s["location"] == "rooftop-unique" for s in response.json())


def test_clear_readings_requires_api_key():
    reg = client.post("/sensors", json={"name": "clear-noauth", "location": "lab"}).json()
    response = client.delete(f"/sensors/{reg['id']}/readings", headers={"x-api-key": "wrong"})
    assert response.status_code == 401


def test_clear_readings_removes_them():
    reg = client.post("/sensors", json={"name": "clear-ok", "location": "lab"}).json()
    for v in (1.0, 2.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    assert client.get(f"/sensors/{reg['id']}/latest").status_code == 200
    response = client.delete(f"/sensors/{reg['id']}/readings", headers={"x-api-key": reg["api_key"]})
    assert response.status_code == 204
    assert client.get(f"/sensors/{reg['id']}/latest").status_code == 404


def test_readings_by_unit_filters():
    reg = client.post("/sensors", json={"name": "unit-filter", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 50.0, "unit": "percent"}, reg["api_key"])
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 22.0, "unit": "celsius"}, reg["api_key"])
    response = client.get("/readings/by-unit/percent?limit=20")
    assert response.status_code == 200
    assert all(r["unit"] == "percent" for r in response.json())


def test_readings_by_unit_bad_limit():
    assert client.get("/readings/by-unit/celsius?limit=0").status_code == 400


def test_search_rejects_short_query():
    assert client.get("/sensors/search?q=a").status_code == 400


def test_search_finds_by_name():
    client.post("/sensors", json={"name": "needle-sensor-xyz", "location": "lab"}).json()
    response = client.get("/sensors/search?q=needle-sensor-xyz")
    assert response.status_code == 200
    body = response.json()
    assert any(s["name"] == "needle-sensor-xyz" for s in body)


def test_search_finds_by_location():
    client.post("/sensors", json={"name": "loc-test", "location": "rooftop-unique"}).json()
    response = client.get("/sensors/search?q=rooftop-unique")
    assert response.status_code == 200
    assert any(s["location"] == "rooftop-unique" for s in response.json())


def test_clear_readings_requires_api_key():
    reg = client.post("/sensors", json={"name": "clear-noauth", "location": "lab"}).json()
    response = client.delete(f"/sensors/{reg['id']}/readings", headers={"x-api-key": "wrong"})
    assert response.status_code == 401


def test_clear_readings_removes_them():
    reg = client.post("/sensors", json={"name": "clear-ok", "location": "lab"}).json()
    for v in (1.0, 2.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    assert client.get(f"/sensors/{reg['id']}/latest").status_code == 200
    response = client.delete(f"/sensors/{reg['id']}/readings", headers={"x-api-key": reg["api_key"]})
    assert response.status_code == 204
    assert client.get(f"/sensors/{reg['id']}/latest").status_code == 404


def test_readings_by_unit_filters():
    reg = client.post("/sensors", json={"name": "unit-filter", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 50.0, "unit": "percent"}, reg["api_key"])
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 22.0, "unit": "celsius"}, reg["api_key"])
    response = client.get("/readings/by-unit/percent?limit=20")
    assert response.status_code == 200
    body = response.json()
    assert all(r["unit"] == "percent" for r in body)


def test_readings_by_unit_bad_limit():
    assert client.get("/readings/by-unit/celsius?limit=0").status_code == 400


def test_readings_count_returns_int():
    response = client.get("/readings/count")
    assert response.status_code == 200
    assert isinstance(response.json()["count"], int)


def test_readings_filter_by_min_value():
    reg = client.post("/sensors", json={"name": "range-min", "location": "lab"}).json()
    for v in (5.0, 15.0, 25.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/readings?min_value=10")
    assert response.status_code == 200
    body = response.json()
    assert all(r["value"] >= 10 for r in body)
    assert len(body) == 2


def test_readings_filter_by_max_value():
    reg = client.post("/sensors", json={"name": "range-max", "location": "lab"}).json()
    for v in (5.0, 15.0, 25.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/readings?max_value=20")
    assert response.status_code == 200
    body = response.json()
    assert all(r["value"] <= 20 for r in body)
    assert len(body) == 2


def test_readings_filter_rejects_inverted_range():
    reg = client.post("/sensors", json={"name": "range-bad", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/readings?min_value=100&max_value=10")
    assert response.status_code == 400


def test_sensors_by_location_returns_matches():
    client.post("/sensors", json={"name": "by-loc-a", "location": "lab-7"}).json()
    client.post("/sensors", json={"name": "by-loc-b", "location": "lab-7"}).json()
    client.post("/sensors", json={"name": "by-loc-c", "location": "lab-other"}).json()
    response = client.get("/sensors/by-location/lab-7")
    assert response.status_code == 200
    body = response.json()
    assert all(s["location"] == "lab-7" for s in body)
    assert len(body) >= 2


def test_sensors_by_location_empty_when_unknown():
    response = client.get("/sensors/by-location/nowhere-xyz")
    assert response.status_code == 200
    assert response.json() == []


def test_readings_recent_includes_recorded_at():
    reg = client.post("/sensors", json={"name": "ts-sensor", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.5, "unit": "celsius"}, reg["api_key"])
    response = client.get("/readings/recent?limit=5")
    assert response.status_code == 200
    body = response.json()
    matched = [r for r in body if r["sensor_name"] == "ts-sensor"]
    assert matched
    assert matched[0]["recorded_at"] is not None


def test_sensor_readings_count():
    reg = client.post("/sensors", json={"name": "count-per", "location": "lab"}).json()
    for v in (1.0, 2.0, 3.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/readings/count")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["sensor_id"] == reg["id"]


def test_sensor_readings_count_unknown_sensor():
    assert client.get("/sensors/99999/readings/count").status_code == 404


def test_readings_units_returns_list():
    reg = client.post("/sensors", json={"name": "units-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "kelvin"}, reg["api_key"])
    response = client.get("/readings/units")
    assert response.status_code == 200
    assert "kelvin" in response.json()["units"]


def test_sensor_reading_range_empty():
    reg = client.post("/sensors", json={"name": "range-empty", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/readings/range")
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["first"] is None


def test_sensor_reading_range_populated():
    reg = client.post("/sensors", json={"name": "range-pop", "location": "lab"}).json()
    for v in (1.0, 2.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/readings/range")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["first"] is not None
    assert body["last"] is not None


def test_sensor_reading_range_unknown():
    assert client.get("/sensors/99999/readings/range").status_code == 404


def test_firmware_set_and_get_latest():
    response = client.post("/firmware/latest?version=3.0.0&url=https://example.com/fw.bin")
    assert response.status_code == 200
    assert response.json()["version"] == "3.0.0"
    response = client.get("/firmware/latest")
    assert response.json()["version"] == "3.0.0"


def test_firmware_set_latest_requires_version():
    assert client.post("/firmware/latest?version=").status_code == 400


def test_firmware_check_update_available():
    client.post("/firmware/latest?version=5.0.0&url=https://example.com/fw5.bin")
    response = client.get("/firmware/check?current_version=4.0.0")
    assert response.status_code == 200
    body = response.json()
    assert body["update_available"] is True
    assert body["latest"] == "5.0.0"


def test_firmware_check_up_to_date():
    client.post("/firmware/latest?version=5.0.0")
    response = client.get("/firmware/check?current_version=5.0.0")
    assert response.json()["update_available"] is False


def test_firmware_upload_and_download():
    payload = b"FAKE FIRMWARE BINARY \x00\x01\x02\x03"
    response = client.post("/firmware/upload?version=7.0.0", content=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "7.0.0"
    assert body["size"] == len(payload)
    response = client.get("/firmware/download/7.0.0")
    assert response.status_code == 200
    assert response.content == payload


def test_firmware_upload_rejects_empty():
    response = client.post("/firmware/upload?version=8.0.0", content=b"")
    assert response.status_code == 400


def test_firmware_download_404_for_unknown():
    assert client.get("/firmware/download/nope-9.9.9").status_code == 404


def test_firmware_upload_returns_sha256():
    payload = b"checksum test payload"
    response = client.post("/firmware/upload?version=cs-1.0", content=payload)
    assert response.status_code == 200
    body = response.json()
    import hashlib
    expected = hashlib.sha256(payload).hexdigest()
    assert body["sha256"] == expected


def test_firmware_download_has_sha256_header():
    payload = b"header check payload"
    client.post("/firmware/upload?version=cs-2.0", content=payload)
    response = client.get("/firmware/download/cs-2.0")
    assert response.status_code == 200
    import hashlib
    expected = hashlib.sha256(payload).hexdigest()
    assert response.headers.get("x-sha256") == expected


def test_firmware_versions_lists_uploads():
    client.post("/firmware/upload?version=vlist-1.0", content=b"a")
    client.post("/firmware/upload?version=vlist-2.0", content=b"bb")
    response = client.get("/firmware/versions")
    assert response.status_code == 200
    body = response.json()
    versions = [v["version"] for v in body]
    assert "vlist-1.0" in versions
    assert "vlist-2.0" in versions
    vlist1 = next(v for v in body if v["version"] == "vlist-1.0")
    assert vlist1["size"] == 1
    assert vlist1["sha256"]


def test_firmware_delete_removes_version():
    client.post("/firmware/upload?version=del-1.0", content=b"data")
    assert client.get("/firmware/download/del-1.0").status_code == 200
    response = client.delete("/firmware/del-1.0")
    assert response.status_code == 204
    assert client.get("/firmware/download/del-1.0").status_code == 404


def test_firmware_delete_404_for_unknown():
    assert client.delete("/firmware/never-existed").status_code == 404


def test_sensor_tag_add_and_list():
    reg = client.post("/sensors", json={"name": "tag-add", "location": "lab"}).json()
    response = client.post(
        f"/sensors/{reg['id']}/tags?key=group&value=fleet-a",
        headers={"x-api-key": reg["api_key"]},
    )
    assert response.status_code == 200
    tags = client.get(f"/sensors/{reg['id']}/tags").json()
    assert any(t["key"] == "group" and t["value"] == "fleet-a" for t in tags)


def test_sensor_tag_requires_api_key():
    reg = client.post("/sensors", json={"name": "tag-noauth", "location": "lab"}).json()
    response = client.post(
        f"/sensors/{reg['id']}/tags?key=group&value=x",
        headers={"x-api-key": "wrong"},
    )
    assert response.status_code == 401


def test_sensor_tag_remove():
    reg = client.post("/sensors", json={"name": "tag-rm", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/tags?key=zone&value=z1", headers={"x-api-key": reg["api_key"]})
    response = client.delete(f"/sensors/{reg['id']}/tags/zone", headers={"x-api-key": reg["api_key"]})
    assert response.status_code == 204
    tags = client.get(f"/sensors/{reg['id']}/tags").json()
    assert not any(t["key"] == "zone" for t in tags)


def test_tag_search_finds_sensors():
    reg = client.post("/sensors", json={"name": "search-tag", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/tags?key=role&value=critical", headers={"x-api-key": reg["api_key"]})
    response = client.get("/tags/search?key=role&value=critical")
    assert response.status_code == 200
    assert reg["id"] in response.json()["sensor_ids"]


def test_groups_lists_fleets():
    reg = client.post("/sensors", json={"name": "grp-a", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/tags?key=group&value=alpha", headers={"x-api-key": reg["api_key"]})
    response = client.get("/groups")
    assert response.status_code == 200
    body = response.json()
    assert "alpha" in body


def test_alert_rule_rejects_no_thresholds():
    reg = client.post("/sensors", json={"name": "alert-empty", "location": "lab"}).json()
    response = client.post(f"/alerts/rules?sensor_id={reg['id']}")
    assert response.status_code == 400


def test_alert_triggers_on_high_value():
    reg = client.post("/sensors", json={"name": "alert-high", "location": "lab"}).json()
    client.post(f"/alerts/rules?sensor_id={reg['id']}&threshold_high=50")
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 99.0, "unit": "celsius"}, reg["api_key"])
    history = client.get("/alerts/history?limit=20").json()
    matched = [a for a in history if a["sensor_id"] == reg["id"] and a["type"] == "high"]
    assert matched


def test_alert_triggers_on_low_value():
    reg = client.post("/sensors", json={"name": "alert-low", "location": "lab"}).json()
    client.post(f"/alerts/rules?sensor_id={reg['id']}&threshold_low=10")
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, reg["api_key"])
    history = client.get("/alerts/history?limit=20").json()
    matched = [a for a in history if a["sensor_id"] == reg["id"] and a["type"] == "low"]
    assert matched


def test_alert_history_bad_limit():
    assert client.get("/alerts/history?limit=0").status_code == 400


def test_command_enqueue_and_poll():
    reg = client.post("/sensors", json={"name": "cmd-flow", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/commands?type=reboot")
    assert response.status_code == 200
    cmd_id = response.json()["id"]
    pending = client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": reg["api_key"]}).json()
    assert any(c["id"] == cmd_id and c["type"] == "reboot" for c in pending)


def test_command_poll_marks_delivered():
    reg = client.post("/sensors", json={"name": "cmd-deliver", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/commands?type=ping")
    client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": reg["api_key"]})
    pending2 = client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": reg["api_key"]}).json()
    assert pending2 == []


def test_command_ack():
    reg = client.post("/sensors", json={"name": "cmd-ack", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/commands?type=ping")
    cmd_id = response.json()["id"]
    client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": reg["api_key"]})
    ack = client.post(f"/commands/{cmd_id}/ack?result=pong", headers={"x-api-key": reg["api_key"]})
    assert ack.status_code == 200
    history = client.get(f"/sensors/{reg['id']}/commands/history").json()
    matched = [c for c in history if c["id"] == cmd_id]
    assert matched and matched[0]["status"] == "acked" and matched[0]["result"] == "pong"


def test_command_poll_requires_api_key():
    reg = client.post("/sensors", json={"name": "cmd-noauth", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": "wrong"})
    assert response.status_code == 401


def test_command_ack_unknown_id():
    assert client.post("/commands/no-such-id/ack", headers={"x-api-key": "x"}).status_code == 404


def test_audit_records_command_enqueue():
    reg = client.post("/sensors", json={"name": "audit-cmd", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/commands?type=reboot")
    entries = client.get("/audit/recent?limit=20").json()
    assert any(e["action"] == "command.enqueue" and e["target"] == f"sensor:{reg['id']}" for e in entries)


def test_audit_records_firmware_upload():
    client.post("/firmware/upload?version=audit-fw-1.0", content=b"x")
    entries = client.get("/audit/recent?limit=20").json()
    assert any(e["action"] == "firmware.upload" for e in entries)


def test_audit_bad_limit():
    assert client.get("/audit/recent?limit=0").status_code == 400


def test_firmware_rollout_to_group():
    s1 = client.post("/sensors", json={"name": "roll-1", "location": "lab"}).json()
    s2 = client.post("/sensors", json={"name": "roll-2", "location": "lab"}).json()
    client.post(f"/sensors/{s1['id']}/tags?key=group&value=rollout-test", headers={"x-api-key": s1["api_key"]})
    client.post(f"/sensors/{s2['id']}/tags?key=group&value=rollout-test", headers={"x-api-key": s2["api_key"]})
    response = client.post("/firmware/rollout?group=rollout-test&version=9.9.9")
    assert response.status_code == 200
    body = response.json()
    assert len(body["targets"]) == 2
    for t in body["targets"]:
        pending = client.get(f"/sensors/{t['sensor_id']}/commands/pending",
                             headers={"x-api-key": (s1 if t['sensor_id'] == s1['id'] else s2)["api_key"]}).json()
        assert any(c["type"] == "ota-update" and c["payload"]["version"] == "9.9.9" for c in pending)


def test_firmware_rollout_unknown_group():
    assert client.post("/firmware/rollout?group=no-such-group&version=1.0").status_code == 404


def test_firmware_rollout_validates():
    assert client.post("/firmware/rollout?group=&version=1.0").status_code == 400


def test_readings_window_returns_after_since():
    reg = client.post("/sensors", json={"name": "win-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, reg["api_key"])
    import time as _t
    _t.sleep(0.05)
    from datetime import datetime as _dt
    cutoff = _dt.utcnow().isoformat()
    _t.sleep(0.05)
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 2.0, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/readings/window?since={cutoff}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["value"] == 2.0


def test_readings_window_rejects_bad_iso():
    reg = client.post("/sensors", json={"name": "win-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/readings/window?since=not-a-date").status_code == 400


def test_readings_window_unknown_sensor():
    assert client.get("/sensors/99999/readings/window").status_code == 404


def test_active_alerts_lists_recent():
    reg = client.post("/sensors", json={"name": "active-alert", "location": "lab"}).json()
    client.post(f"/alerts/rules?sensor_id={reg['id']}&threshold_high=10")
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 99.0, "unit": "celsius"}, reg["api_key"])
    response = client.get("/alerts/active")
    assert response.status_code == 200
    body = response.json()
    matched = [a for a in body if a["sensor_id"] == reg["id"]]
    assert matched
    assert "timestamp" in matched[0]


def test_fleet_summary_shape():
    response = client.get("/fleet/summary")
    assert response.status_code == 200
    body = response.json()
    for key in ("sensors", "readings", "groups", "group_names", "active_alerts", "firmware_latest"):
        assert key in body
    assert isinstance(body["sensors"], int)
    assert isinstance(body["readings"], int)
    assert isinstance(body["group_names"], list)


def test_fleet_summary_reflects_state():
    before = client.get("/fleet/summary").json()
    client.post("/sensors", json={"name": "fleet-bump", "location": "lab"})
    after = client.get("/fleet/summary").json()
    assert after["sensors"] >= before["sensors"] + 1


def test_sensor_aggregate_buckets():
    reg = client.post("/sensors", json={"name": "agg-test", "location": "lab"}).json()
    for v in (1, 2, 3, 4, 5, 6):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": float(v), "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/aggregate?window=6&bucket=3")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["count"] == 3
    assert body[1]["count"] == 3


def test_sensor_aggregate_bad_params():
    reg = client.post("/sensors", json={"name": "agg-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/aggregate?window=0&bucket=1").status_code == 400
    assert client.get(f"/sensors/{reg['id']}/aggregate?window=10&bucket=100").status_code == 400


def test_alerts_clear_empties_history():
    reg = client.post("/sensors", json={"name": "clr-alert", "location": "lab"}).json()
    client.post(f"/alerts/rules?sensor_id={reg['id']}&threshold_high=1")
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 99.0, "unit": "celsius"}, reg["api_key"])
    assert len(client.get("/alerts/history").json()) > 0
    assert client.delete("/alerts/clear").status_code == 204
    assert client.get("/alerts/history").json() == []


def test_alert_rules_list_and_delete():
    reg = client.post("/sensors", json={"name": "rules-test", "location": "lab"}).json()
    client.post(f"/alerts/rules?sensor_id={reg['id']}&threshold_high=50")
    rules = client.get("/alerts/rules").json()
    assert any(r["sensor_id"] == reg["id"] for r in rules)
    matching = [r for r in rules if r["sensor_id"] == reg["id"]]
    idx = matching[0]["index"]
    assert client.delete(f"/alerts/rules/{idx}").status_code == 204


def test_alert_rule_delete_bad_index():
    assert client.delete("/alerts/rules/99999").status_code == 404


def test_admin_pending_commands_view():
    reg = client.post("/sensors", json={"name": "admin-pending", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/commands?type=admin-test-cmd")
    response = client.get("/commands/pending/all")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert any(c["sensor_id"] == reg["id"] and c["type"] == "admin-test-cmd" for c in body["commands"])


def test_sensors_bulk_create():
    payload = [
        {"name": "bulk-1", "location": "lab"},
        {"name": "bulk-2", "location": "lab"},
        {"name": "bulk-3", "location": "lab"},
    ]
    response = client.post("/sensors/bulk", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["count"] == 3


def test_sensors_bulk_empty():
    assert client.post("/sensors/bulk", json=[]).status_code == 400


def test_sensors_bulk_too_many():
    payload = [{"name": f"too-{i}", "location": "lab"} for i in range(101)]
    assert client.post("/sensors/bulk", json=payload).status_code == 400


def test_health_detail_shape():
    response = client.get("/health/detail")
    assert response.status_code == 200
    body = response.json()
    for k in ("status", "uptime_seconds", "sensors", "readings", "last_reading_at", "db_size_bytes"):
        assert k in body
    assert body["status"] == "ok"


def test_sensors_pagination_limits_results():
    for i in range(5):
        client.post("/sensors", json={"name": f"page-{i}", "location": "lab"})
    response = client.get("/sensors?limit=3")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_sensors_pagination_rejects_bad_params():
    assert client.get("/sensors?offset=-1").status_code == 400
    assert client.get("/sensors?limit=0").status_code == 400
    assert client.get("/sensors?limit=9999").status_code == 400


def test_readings_cleanup_bad_days():
    assert client.delete("/readings/cleanup?days=0").status_code == 400
    assert client.delete("/readings/cleanup?days=99999").status_code == 400


def test_readings_cleanup_returns_count():
    response = client.delete("/readings/cleanup?days=1")
    assert response.status_code == 200
    body = response.json()
    assert "deleted" in body
    assert body["older_than_days"] == 1


def test_sensor_disable_marks_state():
    reg = client.post("/sensors", json={"name": "dis-test", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/disable", headers={"x-api-key": reg["api_key"]})
    assert response.status_code == 200
    tags = client.get(f"/sensors/{reg['id']}/tags").json()
    assert any(t["key"] == "state" and t["value"] == "disabled" for t in tags)


def test_sensor_enable_marks_state():
    reg = client.post("/sensors", json={"name": "en-test", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/disable", headers={"x-api-key": reg["api_key"]})
    client.post(f"/sensors/{reg['id']}/enable", headers={"x-api-key": reg["api_key"]})
    tags = client.get(f"/sensors/{reg['id']}/tags").json()
    assert any(t["key"] == "state" and t["value"] == "enabled" for t in tags)


def test_sensor_disable_requires_auth():
    reg = client.post("/sensors", json={"name": "dis-noauth", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/disable", headers={"x-api-key": "wrong"}).status_code == 401


def test_disabled_sensor_rejects_readings():
    reg = client.post("/sensors", json={"name": "no-readings", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/disable", headers={"x-api-key": reg["api_key"]})
    response = _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, reg["api_key"])
    assert response.status_code == 403


def test_audit_search_filters_by_action():
    reg = client.post("/sensors", json={"name": "audit-search", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/commands?type=ping")
    response = client.get("/audit/search?action=command")
    assert response.status_code == 200
    assert all(e["action"].startswith("command") for e in response.json())


def test_audit_search_bad_limit():
    assert client.get("/audit/search?limit=0").status_code == 400


def test_sensor_tags_dict_returns_flat_map():
    reg = client.post("/sensors", json={"name": "tag-dict", "location": "lab"}).json()
    client.post(f"/sensors/{reg['id']}/tags?key=group&value=alpha", headers={"x-api-key": reg["api_key"]})
    client.post(f"/sensors/{reg['id']}/tags?key=zone&value=z1", headers={"x-api-key": reg["api_key"]})
    response = client.get(f"/sensors/{reg['id']}/tags/dict")
    assert response.status_code == 200
    body = response.json()
    assert body["group"] == "alpha"
    assert body["zone"] == "z1"


def test_firmware_check_all_no_latest():
    response = client.get("/firmware/check-all")
    assert response.status_code == 200
    body = response.json()
    assert "devices" in body


def test_firmware_check_all_with_reported():
    client.post("/firmware/latest?version=ck-all-1.0")
    reg = client.post("/sensors", json={"name": "fw-check-all", "location": "lab"}).json()
    client.post(f"/firmware/report?sensor_id={reg['id']}&version=ck-all-1.0", headers={"x-api-key": reg["api_key"]})
    response = client.get("/firmware/check-all")
    body = response.json()
    matched = [d for d in body["devices"] if d["sensor_id"] == reg["id"]]
    assert matched and matched[0]["up_to_date"] is True


def test_inactive_sensors_includes_no_readings():
    reg = client.post("/sensors", json={"name": "never-reported", "location": "lab"}).json()
    response = client.get("/sensors/inactive?minutes=1")
    assert response.status_code == 200
    body = response.json()
    assert any(s["sensor_id"] == reg["id"] and s["last_seen"] is None for s in body)


def test_inactive_sensors_bad_minutes():
    assert client.get("/sensors/inactive?minutes=0").status_code == 400


def test_group_stats_aggregates():
    s1 = client.post("/sensors", json={"name": "gs-1", "location": "lab"}).json()
    s2 = client.post("/sensors", json={"name": "gs-2", "location": "lab"}).json()
    client.post(f"/sensors/{s1['id']}/tags?key=group&value=stats-grp", headers={"x-api-key": s1["api_key"]})
    client.post(f"/sensors/{s2['id']}/tags?key=group&value=stats-grp", headers={"x-api-key": s2["api_key"]})
    _signed_post("/readings", {"sensor_id": s1["id"], "value": 10.0, "unit": "celsius"}, s1["api_key"])
    _signed_post("/readings", {"sensor_id": s2["id"], "value": 30.0, "unit": "celsius"}, s2["api_key"])
    response = client.get("/groups/stats-grp/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["sensor_count"] == 2
    assert body["reading_count"] == 2
    assert body["min"] == 10.0
    assert body["max"] == 30.0


def test_group_stats_unknown_group():
    assert client.get("/groups/no-such/stats").status_code == 404


def test_duplicates_finds_matching_names():
    client.post("/sensors", json={"name": "dup-name-aaa", "location": "site-1"})
    client.post("/sensors", json={"name": "dup-name-aaa", "location": "site-2"})
    response = client.get("/sensors/duplicates")
    assert response.status_code == 200
    body = response.json()
    assert "dup-name-aaa" in body
    assert len(body["dup-name-aaa"]) >= 2


def test_can_stats_shape():
    response = client.get("/can/stats")
    assert response.status_code == 200
    body = response.json()
    for k in ("frames_received", "errors", "buffer_size", "per_sensor"):
        assert k in body


def test_can_frames_recent_returns_list():
    response = client.get("/can/frames/recent")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_can_frames_recent_bad_limit():
    assert client.get("/can/frames/recent?limit=0").status_code == 400
    assert client.get("/can/frames/recent?limit=9999").status_code == 400


def test_can_buffer_records_frames():
    from app.can.buffer import buffer
    buffer.record(0x101, 42, 22.5, "celsius")
    response = client.get("/can/frames/recent?limit=10")
    body = response.json()
    matched = [f for f in body if f["sensor_id"] == 42 and f["value"] == 22.5]
    assert matched


def test_fleet_summary_includes_can():
    response = client.get("/fleet/summary")
    body = response.json()
    assert "can_frames_received" in body
    assert "can_errors" in body


def test_can_frames_by_sensor_filters():
    from app.can.buffer import buffer
    buffer.record(0x200, 777, 99.0, "celsius")
    buffer.record(0x201, 888, 11.0, "celsius")
    response = client.get("/can/frames/by-sensor/777")
    body = response.json()
    assert all(f["sensor_id"] == 777 for f in body)


def test_can_reset_clears_buffer():
    from app.can.buffer import buffer
    buffer.record(0x300, 100, 5.0, "celsius")
    assert buffer.stats()["frames_received"] >= 1
    assert client.delete("/can/reset").status_code == 204
    assert buffer.stats()["frames_received"] == 0


def test_readings_since_returns_newer():
    reg = client.post("/sensors", json={"name": "since-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, reg["api_key"])
    first = client.get("/readings/since/0?limit=1000").json()
    last_id = max((r["id"] for r in first), default=0)
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 2.0, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/readings/since/{last_id}")
    assert response.status_code == 200
    body = response.json()
    assert all(r["id"] > last_id for r in body)


def test_readings_since_bad_limit():
    assert client.get("/readings/since/0?limit=0").status_code == 400


def test_last_value_returns_value():
    reg = client.post("/sensors", json={"name": "lv-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 42.5, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/value/last")
    assert response.status_code == 200
    body = response.json()
    assert body["value"] == 42.5


def test_last_value_null_when_empty():
    reg = client.post("/sensors", json={"name": "lv-empty", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/value/last")
    body = response.json()
    assert body["value"] is None


def test_sensor_rate_calculates():
    reg = client.post("/sensors", json={"name": "rate-test", "location": "lab"}).json()
    for v in (1.0, 2.0, 3.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/rate?minutes=5")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["window_minutes"] == 5


def test_sensor_rate_bad_minutes():
    reg = client.post("/sensors", json={"name": "rate-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/rate?minutes=0").status_code == 400


def test_stuck_sensor_flags_constant():
    reg = client.post("/sensors", json={"name": "stuck-yes", "location": "lab"}).json()
    for _ in range(5):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": 20.0, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/stuck?samples=5")
    body = response.json()
    assert body["stuck"] is True


def test_stuck_sensor_not_stuck_when_varying():
    reg = client.post("/sensors", json={"name": "stuck-no", "location": "lab"}).json()
    for v in (1.0, 2.0, 3.0, 4.0, 5.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/stuck?samples=5")
    body = response.json()
    assert body["stuck"] is False


def test_anomalies_finds_outliers():
    reg = client.post("/sensors", json={"name": "anom-test", "location": "lab"}).json()
    for _ in range(15):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": 20.0, "unit": "celsius"}, reg["api_key"])
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 200.0, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/anomalies?window=20&sigma=2")
    body = response.json()
    assert any(a["value"] == 200.0 for a in body["anomalies"])


def test_anomalies_not_enough_data():
    reg = client.post("/sensors", json={"name": "anom-tiny", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/anomalies?window=100")
    assert response.status_code == 200
    body = response.json()
    assert body["anomalies"] == []


def test_anomalies_bad_window():
    reg = client.post("/sensors", json={"name": "anom-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/anomalies?window=1").status_code == 400


def test_fleet_health_shape():
    response = client.get("/fleet/health")
    assert response.status_code == 200
    body = response.json()
    for k in ("total", "active_count", "active_pct", "fw_uptodate_pct", "status"):
        assert k in body
    assert body["status"] in ("healthy", "degraded", "unhealthy", "empty")


def test_export_csv_returns_csv():
    reg = client.post("/sensors", json={"name": "csv-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 11.5, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    text = response.text
    assert "id,sensor_id,value,unit,recorded_at" in text
    assert "11.5" in text


def test_export_csv_unknown_sensor():
    assert client.get("/sensors/99999/export.csv").status_code == 404


def test_export_all_csv_with_filter():
    reg = client.post("/sensors", json={"name": "all-csv", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 7.5, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/readings/export.csv?sensor_id={reg['id']}")
    assert response.status_code == 200
    assert "sensor_name" in response.text
    assert "all-csv" in response.text


def test_export_all_csv_bad_limit():
    assert client.get("/readings/export.csv?limit=0").status_code == 400


def test_command_cancel_pending():
    reg = client.post("/sensors", json={"name": "cancel-test", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/commands?type=will-cancel")
    cmd_id = response.json()["id"]
    cancel = client.post(f"/commands/{cmd_id}/cancel")
    assert cancel.status_code == 200
    history = client.get(f"/sensors/{reg['id']}/commands/history").json()
    matched = [c for c in history if c["id"] == cmd_id]
    assert matched and matched[0]["status"] == "cancelled"


def test_command_cancel_unknown():
    assert client.post("/commands/no-such-cmd/cancel").status_code == 404


def test_command_cancel_already_delivered():
    reg = client.post("/sensors", json={"name": "cancel-late", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/commands?type=late-cancel")
    cmd_id = response.json()["id"]
    client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": reg["api_key"]})
    cancel = client.post(f"/commands/{cmd_id}/cancel")
    assert cancel.status_code == 409


def test_percentiles_returns_values():
    reg = client.post("/sensors", json={"name": "pct-test", "location": "lab"}).json()
    for v in range(1, 21):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": float(v), "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/percentiles?window=20")
    body = response.json()
    assert body["count"] == 20
    assert body["p50"] >= 10 and body["p50"] <= 11
    assert body["p99"] >= 19


def test_percentiles_empty_sensor():
    reg = client.post("/sensors", json={"name": "pct-empty", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/percentiles")
    body = response.json()
    assert body["count"] == 0 and body["p50"] is None


def test_percentiles_bad_window():
    reg = client.post("/sensors", json={"name": "pct-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/percentiles?window=1").status_code == 400


def test_trend_detects_rising():
    reg = client.post("/sensors", json={"name": "trend-up", "location": "lab"}).json()
    for v in range(1, 11):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": float(v), "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/trend?window=10")
    body = response.json()
    assert body["direction"] == "rising"
    assert body["slope"] > 0


def test_trend_detects_falling():
    reg = client.post("/sensors", json={"name": "trend-down", "location": "lab"}).json()
    for v in range(10, 0, -1):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": float(v), "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/trend?window=10")
    body = response.json()
    assert body["direction"] == "falling"


def test_trend_bad_window():
    reg = client.post("/sensors", json={"name": "trend-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/trend?window=1").status_code == 400


def test_threshold_violations_counts_above():
    reg = client.post("/sensors", json={"name": "tv-test", "location": "lab"}).json()
    for v in (5.0, 50.0, 100.0, 25.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/threshold-violations?max_value=30")
    body = response.json()
    assert body["violations"] == 2
    assert all(i["kind"] == "above" for i in body["items"])


def test_threshold_violations_requires_bound():
    reg = client.post("/sensors", json={"name": "tv-nobound", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/threshold-violations").status_code == 400


def test_sensor_note_add_and_list():
    reg = client.post("/sensors", json={"name": "note-test", "location": "lab"}).json()
    response = client.post(
        f"/sensors/{reg['id']}/notes?text=replaced+battery+on+2026-05-20",
        headers={"x-api-key": reg["api_key"]},
    )
    assert response.status_code == 200
    notes = client.get(f"/sensors/{reg['id']}/notes").json()
    assert any("battery" in n["text"] for n in notes)


def test_sensor_note_requires_auth():
    reg = client.post("/sensors", json={"name": "note-noauth", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/notes?text=hi", headers={"x-api-key": "wrong"}).status_code == 401


def test_sensor_note_validation():
    reg = client.post("/sensors", json={"name": "note-bad", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/notes?text=", headers={"x-api-key": reg["api_key"]}).status_code == 400


def test_distribution_returns_buckets():
    reg = client.post("/sensors", json={"name": "dist-test", "location": "lab"}).json()
    for v in range(1, 11):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": float(v), "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/readings/distribution/{reg['id']}?bins=5&window=10")
    body = response.json()
    assert body["count"] == 10
    assert len(body["buckets"]) == 5
    assert sum(b["count"] for b in body["buckets"]) == 10


def test_distribution_bad_bins():
    reg = client.post("/sensors", json={"name": "dist-bad", "location": "lab"}).json()
    assert client.get(f"/readings/distribution/{reg['id']}?bins=1").status_code == 400


def test_sensor_copy_creates_new():
    reg = client.post("/sensors", json={"name": "to-copy", "location": "site-A"}).json()
    client.post(f"/sensors/{reg['id']}/tags?key=group&value=copy-grp", headers={"x-api-key": reg["api_key"]})
    response = client.post(f"/sensors/{reg['id']}/copy?new_name=copied-sensor")
    assert response.status_code == 201
    copy = response.json()
    assert copy["name"] == "copied-sensor"
    assert copy["location"] == "site-A"
    assert copy["id"] != reg["id"]
    copy_tags = client.get(f"/sensors/{copy['id']}/tags").json()
    assert any(t["key"] == "group" and t["value"] == "copy-grp" for t in copy_tags)


def test_sensor_copy_unknown():
    assert client.post("/sensors/99999/copy").status_code == 404


def test_keep_alive_updates_last_seen():
    reg = client.post("/sensors", json={"name": "alive-test", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/keep-alive", headers={"x-api-key": reg["api_key"]})
    assert response.status_code == 200
    last_seen = response.json()["last_seen"]
    fetched = client.get(f"/sensors/{reg['id']}/last-seen").json()
    assert fetched["last_seen"] == last_seen


def test_keep_alive_requires_auth():
    reg = client.post("/sensors", json={"name": "alive-noauth", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/keep-alive", headers={"x-api-key": "wrong"}).status_code == 401


def test_last_seen_null_when_unseen():
    reg = client.post("/sensors", json={"name": "alive-never", "location": "lab"}).json()
    body = client.get(f"/sensors/{reg['id']}/last-seen").json()
    assert body["last_seen"] is None


def test_sensor_restart_enqueues_command():
    reg = client.post("/sensors", json={"name": "restart-test", "location": "lab"}).json()
    response = client.post(f"/sensors/{reg['id']}/restart")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "restart"
    pending = client.get(f"/sensors/{reg['id']}/commands/pending", headers={"x-api-key": reg["api_key"]}).json()
    assert any(c["id"] == body["command_id"] and c["type"] == "restart" for c in pending)


def test_sensor_restart_unknown():
    assert client.post("/sensors/99999/restart").status_code == 404


def test_udp_stats_shape():
    response = client.get("/udp/stats")
    assert response.status_code == 200
    body = response.json()
    for k in ("packets", "errors", "bytes_received", "last_packet_at", "per_sensor"):
        assert k in body


def test_udp_stats_records_packet():
    from app.net.udp_receiver import stats
    stats.record_packet(64, 999)
    body = client.get("/udp/stats").json()
    assert body["packets"] >= 1
    assert "999" in body["per_sensor"] or 999 in body["per_sensor"]


def test_tcp_stats_shape():
    response = client.get("/tcp/stats")
    assert response.status_code == 200
    body = response.json()
    for k in ("connections_opened", "active_connections", "readings_received", "errors"):
        assert k in body


def test_tcp_stats_shape():
    response = client.get("/tcp/stats")
    assert response.status_code == 200
    body = response.json()
    for k in ("connections_opened", "active_connections", "readings_received", "errors"):
        assert k in body


def test_fleet_summary_includes_udp_tcp():
    body = client.get("/fleet/summary").json()
    for k in ("udp_packets", "tcp_active_connections", "tcp_readings_received"):
        assert k in body


def test_net_health_shape():
    body = client.get("/net/health").json()
    for transport in ("can", "udp", "tcp"):
        assert transport in body
        assert "error_pct" in body[transport]


def test_net_health_error_rate():
    from app.net.udp_receiver import stats
    stats.record_error()
    body = client.get("/net/health").json()
    assert body["udp"]["error_pct"] >= 0


def test_udp_reset_clears_counters():
    from app.net.udp_receiver import stats
    stats.record_packet(64, 1)
    assert stats.snapshot()["packets"] >= 1
    assert client.delete("/udp/reset").status_code == 204
    assert stats.snapshot()["packets"] == 0


def test_tcp_reset_clears_counters():
    from app.net.tcp_server import stats
    stats.conn_opened()
    stats.reading_ok()
    assert client.delete("/tcp/reset").status_code == 204
    assert stats.snapshot()["readings_received"] == 0


def test_sensor_health_no_data():
    reg = client.post("/sensors", json={"name": "health-nodata", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "no-data"


def test_sensor_health_healthy():
    reg = client.post("/sensors", json={"name": "health-ok", "location": "lab"}).json()
    for v in (1.0, 2.0, 3.0, 4.0, 5.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/health")
    body = response.json()
    assert body["active"] is True
    assert body["stuck"] is False


def test_sensor_health_stuck():
    reg = client.post("/sensors", json={"name": "health-stuck", "location": "lab"}).json()
    for _ in range(6):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": 20.0, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/health")
    assert response.json()["stuck"] is True


def test_compare_sensors_difference():
    a = client.post("/sensors", json={"name": "cmp-a", "location": "lab"}).json()
    b = client.post("/sensors", json={"name": "cmp-b", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": a["id"], "value": 30.0, "unit": "celsius"}, a["api_key"])
    _signed_post("/readings", {"sensor_id": b["id"], "value": 10.0, "unit": "celsius"}, b["api_key"])
    response = client.get(f"/sensors/{a['id']}/compare/{b['id']}")
    body = response.json()
    assert body["avg_a"] == 30.0
    assert body["avg_b"] == 10.0
    assert body["difference"] == 20.0


def test_compare_sensors_unknown():
    a = client.post("/sensors", json={"name": "cmp-solo", "location": "lab"}).json()
    assert client.get(f"/sensors/{a['id']}/compare/99999").status_code == 404


def test_locations_lists_with_counts():
    client.post("/sensors", json={"name": "loc-1", "location": "warehouse-z"})
    client.post("/sensors", json={"name": "loc-2", "location": "warehouse-z"})
    response = client.get("/locations")
    assert response.status_code == 200
    body = response.json()
    wz = [l for l in body if l["location"] == "warehouse-z"]
    assert wz and wz[0]["sensor_count"] >= 2


def test_reset_key_changes_key():
    reg = client.post("/sensors", json={"name": "rotate-key", "location": "lab"}).json()
    old_key = reg["api_key"]
    response = client.post(f"/sensors/{reg['id']}/reset-key", headers={"x-api-key": old_key})
    assert response.status_code == 200
    new_key = response.json()["api_key"]
    assert new_key != old_key
    # old key no longer works
    bad = _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, old_key)
    assert bad.status_code == 401
    # new key works
    good = _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, new_key)
    assert good.status_code == 201


def test_reset_key_requires_current_key():
    reg = client.post("/sensors", json={"name": "rotate-noauth", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/reset-key", headers={"x-api-key": "wrong"}).status_code == 401


def test_sensor_summary_full():
    reg = client.post("/sensors", json={"name": "summ-test", "location": "lab"}).json()
    for v in (10.0, 20.0, 30.0):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": v, "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["reading_count"] == 3
    assert body["latest_value"] == 30.0
    assert body["stats"]["min"] == 10.0
    assert body["stats"]["max"] == 30.0
    assert body["stats"]["avg"] == 20.0


def test_sensor_summary_empty():
    reg = client.post("/sensors", json={"name": "summ-empty", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/summary")
    body = response.json()
    assert body["reading_count"] == 0
    assert body["latest_value"] is None


def test_sensor_summary_unknown():
    assert client.get("/sensors/99999/summary").status_code == 404


def test_latest_per_sensor_includes_all():
    reg = client.post("/sensors", json={"name": "lps-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 55.5, "unit": "celsius"}, reg["api_key"])
    response = client.get("/readings/latest-per-sensor")
    assert response.status_code == 200
    body = response.json()
    matched = [r for r in body if r["sensor_id"] == reg["id"]]
    assert matched and matched[0]["value"] == 55.5


def test_moving_average_computes():
    reg = client.post("/sensors", json={"name": "ma-test", "location": "lab"}).json()
    for v in range(1, 11):
        _signed_post("/readings", {"sensor_id": reg["id"], "value": float(v), "unit": "celsius"}, reg["api_key"])
    response = client.get(f"/sensors/{reg['id']}/moving-average?period=3&points=10")
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == 3
    assert len(body["series"]) == 8
    assert body["series"][0]["ma"] == 2.0


def test_moving_average_bad_period():
    reg = client.post("/sensors", json={"name": "ma-bad", "location": "lab"}).json()
    assert client.get(f"/sensors/{reg['id']}/moving-average?period=1").status_code == 400


def test_rename_sensor_changes_name():
    reg = client.post("/sensors", json={"name": "old-name", "location": "lab"}).json()
    response = client.post(
        f"/sensors/{reg['id']}/rename?name=new-name",
        headers={"x-api-key": reg["api_key"]},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "new-name"
    fetched = client.get(f"/sensors/{reg['id']}").json()
    assert fetched["name"] == "new-name"


def test_rename_sensor_requires_auth():
    reg = client.post("/sensors", json={"name": "rn-noauth", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/rename?name=x", headers={"x-api-key": "wrong"}).status_code == 401


def test_rename_sensor_validation():
    reg = client.post("/sensors", json={"name": "rn-bad", "location": "lab"}).json()
    assert client.post(f"/sensors/{reg['id']}/rename?name=", headers={"x-api-key": reg["api_key"]}).status_code == 400


def test_sensor_exists_true():
    reg = client.post("/sensors", json={"name": "exists-yes", "location": "lab"}).json()
    response = client.get(f"/sensors/{reg['id']}/exists")
    assert response.status_code == 200
    assert response.json()["exists"] is True


def test_sensor_exists_false():
    response = client.get("/sensors/99999/exists")
    assert response.status_code == 200
    assert response.json()["exists"] is False


def test_count_by_location():
    client.post("/sensors", json={"name": "cbl-1", "location": "depot-x"})
    client.post("/sensors", json={"name": "cbl-2", "location": "depot-x"})
    response = client.get("/sensors/count/by-location")
    assert response.status_code == 200
    body = response.json()
    assert body.get("depot-x", 0) >= 2


def test_readings_total_counts():
    before = client.get("/readings/total").json()["total_readings"]
    reg = client.post("/sensors", json={"name": "total-test", "location": "lab"}).json()
    _signed_post("/readings", {"sensor_id": reg["id"], "value": 1.0, "unit": "celsius"}, reg["api_key"])
    after = client.get("/readings/total").json()["total_readings"]
    assert after >= before + 1


def test_ping_default():
    response = client.get("/ping")
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "pong"
    assert "server_time" in body


def test_ping_echo():
    response = client.get("/ping?msg=hello")
    assert response.json()["reply"] == "hello"
