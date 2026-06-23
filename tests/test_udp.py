"""Tests for UDP datagram decoding."""
import json
import pytest
from app.net.udp_receiver import decode_datagram, UdpStats


def test_decode_datagram_valid():
    data = json.dumps({"sensor_id": 5, "value": 22.5, "unit": "celsius"}).encode()
    result = decode_datagram(data)
    assert result == {"sensor_id": 5, "value": 22.5, "unit": "celsius"}


def test_decode_datagram_missing_field():
    data = json.dumps({"sensor_id": 5, "value": 22.5}).encode()
    with pytest.raises(ValueError):
        decode_datagram(data)


def test_decode_datagram_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        decode_datagram(b"not json")


def test_decode_datagram_coerces_types():
    data = json.dumps({"sensor_id": "5", "value": "22.5", "unit": "celsius"}).encode()
    result = decode_datagram(data)
    assert result["sensor_id"] == 5
    assert result["value"] == 22.5


def test_udp_stats_tracks_counts():
    s = UdpStats()
    s.record_packet(100, 1)
    s.record_packet(200, 1)
    s.record_packet(50, 2)
    snap = s.snapshot()
    assert snap["packets"] == 3
    assert snap["bytes_received"] == 350
    assert snap["per_sensor"][1] == 2
    assert snap["per_sensor"][2] == 1


def test_udp_stats_errors():
    s = UdpStats()
    s.record_error()
    s.record_error()
    assert s.snapshot()["errors"] == 2
