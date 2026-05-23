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
