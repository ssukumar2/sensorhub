# sensorhub

An IoT sensor telemetry gateway with a Python backend and a C++ sensor client. Sensors register with the backend, receive an API key, and submit readings over HTTP, MQTT, or CAN bus. All three transport paths write to the same SQLite database, so the backend is fully transport-agnostic.

I built this to sharpen my skills in IoT backend design, multi-transport ingestion, authenticated device communication, and cross-language systems integration.

## Architecture

The project is a monorepo with two main components. The backend is written in Python using FastAPI and SQLModel with SQLite for persistence. It handles sensor registration, telemetry ingestion, and data querying through a REST API. The C++ sensor simulator client registers itself, obtains an API key, and publishes temperature readings over HTTP, MQTT, or CAN depending on the command-line flag.

A React frontend provides a live dashboard with sensor status, readings charts, and system metrics. A separate MQTT subscriber process listens on the Mosquitto broker and writes incoming readings to the same database. A CAN receiver decodes SocketCAN frames and does the same.

## Endpoints

- `GET /health` — liveness check, returns service name and status
- `GET /metrics` — prometheus-style metrics (sensor count, reading count, uptime)
- `GET /status` — system overview with transport list and counts
- `GET /version` — API version and supported protocols
- `POST /sensors` — register a new sensor, returns an API key
- `GET /sensors` — list all registered sensors
- `GET /sensors/{id}` — get one sensor by ID
- `PATCH /sensors/{id}` — update sensor name or location (requires API key)
- `DELETE /sensors/{id}` — delete sensor and its readings (requires API key)
- `POST /readings` — submit a single reading (requires API key, optional HMAC signature)
- `POST /readings/batch` — submit multiple readings at once (requires API key)
- `GET /readings` — list readings, optionally filtered by sensor

## Transport options

HTTP REST is the default transport. Every reading request carries an `x-api-key` header. The C++ client optionally signs payloads with HMAC-SHA256 and includes a nonce and timestamp for replay protection. The server verifies the signature when present and rejects requests older than 30 seconds.

MQTT uses a Mosquitto broker on localhost:1883. The C++ client publishes JSON to `sensorhub/sensors/{id}/readings` with QoS 1. A Python subscriber picks up messages and writes them to the database.

CAN bus uses Linux SocketCAN with virtual CAN for development. Readings are packed into 8-byte CAN frames: 2 bytes sensor ID, 4 bytes fixed-point value, 1 byte unit code, 1 byte flags. Each sensor transmits on CAN ID 0x100 + sensor_id. A Python CAN receiver decodes and persists them.

## Security

Each sensor gets a unique API key on registration. Readings require the key in the `x-api-key` header, verified with constant-time comparison. The C++ client signs every payload with HMAC-SHA256. The signature covers the JSON body, a random 128-bit nonce, and a unix timestamp. The server verifies the signature and rejects replayed or expired requests. Rate limiting middleware throttles excessive requests per IP.

## Stack

The backend uses Python 3.8+ with FastAPI, SQLModel, SQLite, Uvicorn, and paho-mqtt. The C++ client is built with C++17 using cpr for HTTP, Eclipse Paho for MQTT, OpenSSL for HMAC, and nlohmann/json for serialization. CMake handles the build with FetchContent for dependencies. The frontend uses React with TypeScript, recharts for data visualization, and communicates with the backend through CORS-enabled REST endpoints. Mosquitto serves as the MQTT broker. pytest covers the backend test suite.

## Running it locally

Clone and set up the Python backend:

    git clone git@github.com:ssukumar2/sensorhub.git
    cd sensorhub
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://localhost:8000/docs for the interactive API documentation.

To run the MQTT subscriber in a separate terminal:

    python3 -m app.mqtt.subscriber

To set up virtual CAN for development:

    sudo ./scripts/setup_vcan.sh

Build and run the C++ client:

    cd client-cpp
    cmake -B build && cmake --build build
    ./build/sensor_client --mode=http
    ./build/sensor_client --mode=mqtt
    ./build/sensor_client --mode=can

Run the frontend:

    cd frontend
    npm install && npm start

## Tests

    source .venv/bin/activate
    pytest tests/ -v

## Documentation

Protocol specifications live in the docs/ folder: docs/can_protocol.md covers the CAN frame layout and virtual CAN setup, and docs/mqtt_protocol.md covers the MQTT topic structure, payload format, and QoS settings.

## License

MIT