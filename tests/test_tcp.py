"""Tests for TCP server parsing and stats."""
import json
import pytest
from app.net.tcp_server import parse_line, TcpStats


def test_parse_line_valid():
    line = json.dumps({"sensor_id": 3, "value": 12.0, "unit": "voltage"}).encode()
    assert parse_line(line) == {"sensor_id": 3, "value": 12.0, "unit": "voltage"}


def test_parse_line_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_line(b"garbage")


def test_parse_line_missing_field():
    with pytest.raises(ValueError):
        parse_line(json.dumps({"sensor_id": 1}).encode())


def test_tcp_stats_lifecycle():
    s = TcpStats()
    s.conn_opened()
    s.conn_opened()
    s.reading_ok()
    s.reading_ok()
    s.reading_ok()
    s.conn_closed()
    snap = s.snapshot()
    assert snap["connections_opened"] == 2
    assert snap["connections_closed"] == 1
    assert snap["active_connections"] == 1
    assert snap["readings_received"] == 3


def test_tcp_stats_error_tracking():
    s = TcpStats()
    s.error()
    assert s.snapshot()["errors"] == 1
