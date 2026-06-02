"""Tests for app/can decode logic."""
import struct
import pytest
from app.can.receiver import decode_frame
from app.can.buffer import FrameBuffer


def make_frame(sensor_id: int, raw_value: int, unit_code: int) -> bytes:
    return struct.pack(">Hi", sensor_id, raw_value) + bytes([unit_code, 0])


def test_decode_frame_celsius():
    frame = make_frame(42, 2250, 0x01)
    decoded = decode_frame(frame)
    assert decoded == {"sensor_id": 42, "value": 22.50, "unit": "celsius"}


def test_decode_frame_negative_value():
    frame = make_frame(1, -1500, 0x01)
    decoded = decode_frame(frame)
    assert decoded["value"] == -15.0


def test_decode_frame_unknown_unit():
    frame = make_frame(7, 100, 0xFF)
    decoded = decode_frame(frame)
    assert decoded["unit"].startswith("unknown_")


def test_decode_frame_rejects_wrong_size():
    with pytest.raises(ValueError):
        decode_frame(b"\x00\x01\x02")


def test_frame_buffer_records_and_returns():
    buf = FrameBuffer(max_size=10)
    buf.record(0x100, 1, 22.0, "celsius")
    buf.record(0x101, 2, 55.0, "percent")
    recent = buf.recent(10)
    assert len(recent) == 2
    assert recent[0]["sensor_id"] == 2  # newest first


def test_frame_buffer_caps_at_max_size():
    buf = FrameBuffer(max_size=3)
    for i in range(10):
        buf.record(0x100 + i, i, float(i), "celsius")
    assert buf.stats()["buffer_size"] == 3
    assert buf.stats()["frames_received"] == 10
