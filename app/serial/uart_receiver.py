"""UART serial receiver for STM32 sensor nodes.

Reads sensor readings from a serial port (e.g. /dev/ttyACM0)
connected to an STM32 Nucleo board. Parses simple text protocol:
    READING:<sensor_id>:<value>:<unit>\n

This bridges bare-metal microcontrollers into the sensorhub backend
without requiring the MCU to speak HTTP or MQTT.
"""
import serial
import logging
import re
from sqlmodel import Session
from app.database import engine
from app.models import Reading, Sensor

log = logging.getLogger("sensorhub.uart")

READING_PATTERN = re.compile(r"^READING:(\d+):([\d.]+):(\w+)$")

def parse_line(line: str) -> dict:
    match = READING_PATTERN.match(line.strip())
    if not match:
        return None
    return {
        "sensor_id": int(match.group(1)),
        "value": float(match.group(2)),
        "unit": match.group(3),
    }

def run(port: str = "/dev/ttyACM0", baudrate: int = 115200):
    log.info("opening %s at %d baud", port, baudrate)
    ser = serial.Serial(port, baudrate, timeout=1)

    while True:
        try:
            raw = ser.readline().decode("utf-8", errors="ignore")
            if not raw:
                continue

            data = parse_line(raw)
            if data is None:
                log.debug("ignored: %s", raw.strip())
                continue

            with Session(engine) as session:
                sensor = session.get(Sensor, data["sensor_id"])
                if sensor is None:
                    log.warning("unknown sensor_id=%d", data["sensor_id"])
                    continue

                reading = Reading(
                    sensor_id=data["sensor_id"],
                    value=data["value"],
                    unit=data["unit"],
                )
                session.add(reading)
                session.commit()

            log.info("UART sensor=%d value=%.2f %s",
                     data["sensor_id"], data["value"], data["unit"])

        except serial.SerialException as e:
            log.error("serial error: %s", e)
            break
        except KeyboardInterrupt:
            break

    ser.close()
    log.info("UART receiver stopped")

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    run(port)
