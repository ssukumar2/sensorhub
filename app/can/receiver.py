"""CAN bus receiver for sensorhub.

Listens on a SocketCAN interface (vcan0 by default) and writes
decoded sensor readings to the database.
"""
import struct
import logging
from sqlmodel import Session
from app.database import engine, init_db
from app.models import Reading, Sensor

log = logging.getLogger("sensorhub.can")

UNIT_MAP = {
    0x01: "celsius", 0x02: "fahrenheit", 0x03: "percent",
    0x04: "hpa", 0x05: "lux", 0x06: "voltage",
    0x07: "ampere", 0x08: "watt",
}


def decode_frame(data: bytes) -> dict:
    """Decode an 8-byte CAN frame into a reading dict."""
    if len(data) != 8:
        raise ValueError(f"expected 8 bytes, got {len(data)}")

    sensor_id = struct.unpack(">H", data[0:2])[0]
    raw_value = struct.unpack(">i", data[2:6])[0]
    unit_code = data[6]

    return {
        "sensor_id": sensor_id,
        "value": raw_value / 100.0,
        "unit": UNIT_MAP.get(unit_code, f"unknown_{unit_code:#x}"),
    }


def main(interface: str = "vcan0"):
    """Main loop: read CAN frames and persist readings."""
    try:
        import socket as _socket
        import struct as _struct
    except ImportError:
        log.error("socket module not available")
        return

    init_db()
    log.info("listening on %s", interface)

    sock = _socket.socket(_socket.AF_CAN, _socket.SOCK_RAW, _socket.CAN_RAW)
    sock.bind((interface,))

    while True:
        frame = sock.recv(16)
        can_id = _struct.unpack("<I", frame[0:4])[0] & 0x1FFFFFFF
        dlc = frame[4]
        data = frame[8:8 + dlc]

        try:
            reading = decode_frame(data)
        except ValueError as e:
            log.warning("bad frame on 0x%X: %s", can_id, e)
            continue

        with Session(engine) as session:
            sensor = session.get(Sensor, reading["sensor_id"])
            if sensor is None:
                log.warning("unknown sensor_id=%d", reading["sensor_id"])
                continue

            r = Reading(
                sensor_id=reading["sensor_id"],
                value=reading["value"],
                unit=reading["unit"],
            )
            session.add(r)
            session.commit()

        log.info("CAN 0x%X -> sensor=%d value=%.2f %s",
                 can_id, reading["sensor_id"], reading["value"], reading["unit"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()