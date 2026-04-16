# sensorhub

A small experimental IoT sensor gateway. Sensors register with the backend, submit telemetry readings, and a REST API exposes the data for querying. The system supports both HTTP and MQTT transport, with API key authentication on sensor readings.

This is a learning project I'm building to sharpen my skills in backend design, IoT ingestion patterns, authenticated device communication, and multi-language systems integration.

## Architecture

The project is a monorepo with two main components:

- **Python backend** (FastAPI + SQLModel + SQLite) that handles sensor registration, reading ingestion over both HTTP REST and MQTT, and data querying
- **C++ sensor simulator client** that registers itself, obtains an API key, and publishes temperature readings either over HTTP or MQTT

Both transport paths write into the same SQLite database, so the backend is agnostic to how readings arrive.

## Endpoints

- `GET /health` — liveness probe
- `POST /sensors` — register a new sensor and receive an API key
- `GET /sensors` — list all registered sensors
- `GET /sensors/{id}` — get details of one sensor
- `POST /readings` — submit a telemetry reading (requires `x-api-key` header)
- `GET /sensors/{id}/readings` — list recent readings for a sensor

## Transport options

- **HTTP REST** with API key authentication via `x-api-key` header
- **MQTT** over a Mosquitto broker, topic pattern `sensorhub/sensors/{id}/readings`

## Stack

- Python 3.8+ with FastAPI, SQLModel, SQLite, Uvicorn, paho-mqtt
- C++17 client with cpr (HTTP) and Eclipse Paho (MQTT)
- CMake build system with FetchContent for dependencies
- Mosquitto MQTT broker
- pytest for backend tests

## Running it locally

Install Mosquitto if you want to try MQTT:

    sudo apt install mosquitto mosquitto-clients

Clone and set up the Python side:

    git clone git@github.com:ssukumar2/sensorhub.git
    cd sensorhub
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Run the backend:

    uvicorn app.main:app --reload

Then open http://localhost:8000/docs for the interactive API docs.

To run the MQTT subscriber in a separate terminal:

    python3 -m app.mqtt.subscriber

Build and run the C++ client:

    cd client-cpp
    cmake -B build && cmake --build build
    ./build/sensor_client --mode=http
    # or in MQTT mode:
    ./build/sensor_client --mode=mqtt

## Tests

    pytest tests/ -v

## Status

Working:
- HTTP REST with API key authentication
- MQTT ingestion alongside HTTP, both writing to the same database
- C++ client with BackendClient and MqttClient classes
- pytest suite covering the main endpoints

Planned next:
- GitHub Actions CI/CD for backend tests and C++ build
- Replay protection and HMAC-signed requests
- TLS for HTTP and MQTT
- Dashboard frontend in React/TypeScript
- Yocto deployment (separate companion repo)


## License

MIT