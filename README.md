![Python Tests](https://github.com/ssukumar2/sensorhub/actions/workflows/python-tests.yml/badge.svg)

# sensorhub

An IoT sensor gateway that receives telemetry data from sensor devices, stores it in a database, and exposes it through a REST API. Sensors register with the backend, get an API key, and then submit readings over HTTP or MQTT. Both transport paths end up in the same SQLite database.

I built this to explore how real IoT backends work — device registration, authenticated ingestion, multiple transport options, and connecting a Python backend with a C++ device client.

## How it works

The backend is a Python FastAPI server with SQLite storage. The client is a C++ program that acts like a real sensor — it registers itself, gets a key, and starts sending temperature readings every 5 seconds.

You can run the client in HTTP mode or MQTT mode. In HTTP mode it makes direct REST calls. In MQTT mode it publishes to a Mosquitto broker, and a Python subscriber picks up the messages and writes them to the database. Either way, the data ends up in the same place and you can query it through the same API.

## Endpoints

- `GET /health` — check if the backend is running
- `GET /metrics` — server uptime and request count
- `POST /sensors` — register a new sensor, get back an API key
- `GET /sensors` — list all sensors
- `GET /sensors/{id}` — get one sensor
- `POST /readings` — submit a reading (needs x-api-key header)
- `GET /sensors/{id}/readings` — get recent readings for a sensor

## Security

Every reading is protected with API key authentication and HMAC-SHA256 signatures. The C++ client signs each payload with the sensor's key, a unique nonce, and a timestamp. The server verifies the signature and rejects tampered or replayed requests older than 30 seconds. All comparisons use constant-time logic to prevent timing attacks.

## Stack

- Python 3.8+, FastAPI, SQLModel, SQLite, Uvicorn, paho-mqtt
- C++17 client with cpr, Eclipse Paho MQTT, nlohmann/json, OpenSSL
- CMake with FetchContent for C++ dependencies
- Mosquitto MQTT broker
- pytest for backend tests
- GitHub Actions CI

## Running it

Set up the Python backend:

    git clone git@github.com:ssukumar2/sensorhub.git
    cd sensorhub
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://localhost:8000/docs to see the API.

For MQTT, install Mosquitto and run the subscriber:

    sudo apt install mosquitto mosquitto-clients
    python3 -m app.mqtt.subscriber

Build and run the C++ client:

    cd client-cpp
    cmake -B build && cmake --build build
    ./build/sensor_client --mode=http
    ./build/sensor_client --mode=mqtt

## Tests

    pytest tests/ -v

Seven tests covering health check, metrics, sensor registration, API key authentication, and reading submission.

## License

MIT