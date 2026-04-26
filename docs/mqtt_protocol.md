# MQTT protocol for sensorhub

## Overview

MQTT is a lightweight publish-subscribe messaging protocol designed for constrained IoT devices. Instead of sending HTTP requests directly, sensors publish messages to named topics on a central broker. The backend subscribes to those topics and receives messages as they arrive. This decouples the sender from the receiver: the sensor doesn't need to know the backend's address, and the backend can handle any number of sensors through a single broker connection.

## Broker

Sensorhub uses Mosquitto as the MQTT broker, running on localhost:1883 with default settings. Install it with:

    sudo apt install mosquitto mosquitto-clients
    sudo systemctl start mosquitto

## Topic structure

Each sensor publishes readings to a topic that includes its sensor ID:

    sensorhub/sensors/{sensor_id}/readings

For example, sensor 3 publishes to `sensorhub/sensors/3/readings`.

The Python subscriber listens on the wildcard pattern `sensorhub/sensors/+/readings`, where the `+` matches any single level. This means the subscriber receives readings from all sensors through one subscription.

## Payload format

Messages are JSON-encoded with two fields:

    {"value": 22.5, "unit": "celsius"}

The sensor_id is extracted from the topic path, not from the payload. This keeps the payload small and avoids redundancy.

## QoS level

All messages use QoS 1 (at-least-once delivery). The broker acknowledges receipt to the sender and delivers to all subscribers. If the network drops before acknowledgment, the sender retries. This means a reading might arrive twice in rare cases, but it will never be silently lost. For sensor telemetry this is the right tradeoff: a duplicate reading is harmless, a lost reading is a gap in your data.

QoS 0 (fire-and-forget) would be faster but risks losing readings on unreliable networks. QoS 2 (exactly-once) adds significant overhead with a four-step handshake per message, which is overkill for telemetry.

## How the pieces connect

The C++ client uses Eclipse Paho to connect to the broker and publish readings. Mosquitto routes them to any connected subscribers. The Python subscriber (app/mqtt/subscriber.py) receives each message, parses the sensor_id from the topic, deserializes the JSON payload, and writes a Reading row to the SQLite database. This is the same database used by the HTTP endpoints, so readings from MQTT and HTTP are indistinguishable once stored.

## Testing with command-line tools

Subscribe to all sensor readings in one terminal:

    mosquitto_sub -h localhost -t "sensorhub/sensors/+/readings" -v

Publish a test reading in another terminal:

    mosquitto_pub -h localhost -t "sensorhub/sensors/1/readings" -m '{"value": 22.5, "unit": "celsius"}'

The subscriber terminal should immediately show the message. This verifies the broker is working before you run any code.

## Running the full pipeline

Terminal 1 — start the backend:

    uvicorn app.main:app --reload

Terminal 2 — start the MQTT subscriber:

    python3 -m app.mqtt.subscriber

Terminal 3 — run the C++ client in MQTT mode:

    cd client-cpp
    ./build/sensor_client --mode=mqtt

You should see readings flow from the C++ client through the broker to the subscriber, and they become queryable through the REST API.