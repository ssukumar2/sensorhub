"""
MQTT subscriber for sensorhub.

Subscribes to sensor reading topics on the Mosquitto broker and
persists incoming readings to the same SQLite database used by
the HTTP API.

Topic structure:
    sensorhub/sensors/{sensor_id}/readings

Payload format (JSON):
    {"value": 22.5, "unit": "celsius"}

The x-api-key equivalent for MQTT is username/password auth at
connect time. For now, runs unauthenticated on localhost only.
"""
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt
from sqlmodel import Session

from app.database import engine, init_db
from app.models import Reading, Sensor

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC_PATTERN = "sensorhub/sensors/+/readings"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def on_connect(client: mqtt.Client, userdata: Any, flags: dict, reason_code, properties=None) -> None:
    """Called when the client connects to the broker."""
    if reason_code == 0:
        log.info("connected to broker at %s:%s", BROKER_HOST, BROKER_PORT)
        client.subscribe(TOPIC_PATTERN, qos=1)
        log.info("subscribed to %s", TOPIC_PATTERN)
    else:
        log.error("connection failed, reason_code=%s", reason_code)


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """Called for every message received on a subscribed topic."""
    try:
        # Parse sensor id from the topic: sensorhub/sensors/{id}/readings
        parts = msg.topic.split("/")
        if len(parts) != 4 or parts[0] != "sensorhub" or parts[3] != "readings":
            log.warning("unexpected topic: %s", msg.topic)
            return

        sensor_id = int(parts[2])

        # Parse payload
        payload = json.loads(msg.payload.decode("utf-8"))
        value = float(payload["value"])
        unit = str(payload["unit"])

        # Persist to DB
        with Session(engine) as session:
            sensor = session.get(Sensor, sensor_id)
            if sensor is None:
                log.warning("reading for unknown sensor_id=%s, dropping", sensor_id)
                return

            reading = Reading(sensor_id=sensor_id, value=value, unit=unit)
            session.add(reading)
            session.commit()

        log.info("stored reading: sensor_id=%s value=%s %s", sensor_id, value, unit)

    except Exception as e:
        log.exception("failed to process message: %s", e)


def main() -> None:
    init_db()

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    log.info("connecting to broker %s:%s", BROKER_HOST, BROKER_PORT)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    client.loop_forever()


if __name__ == "__main__":
    main()