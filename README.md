![Python Tests](https://github.com/ssukumar2/sensorhub/actions/workflows/python-tests.yml/badge.svg)

# sensorhub

An IoT sensor gateway that receives telemetry data from sensor devices, stores it in a database, and exposes it through a REST API. Sensors register with the backend, get an API key, and then submit readings over HTTP or MQTT. Both transport paths end up in the same SQLite database.

I built this to explore how IoT backends work in practice — device registration, authenticated ingestion, dual transport, and the interplay between a Python backend and a C++ device client.

## How it works

The backend is a Python FastAPI server with SQLite storage. The client is a C++ program that pretends to be a real sensor — it registers itself, gets a key, and starts sending fake temperature readings every 5 seconds.

You can run the client in HTTP mode (direct REST calls) or MQTT mode (publishes to a Mosquitto broker, and a Python subscriber picks up the messages and writes them to the database). Either way, the data ends up in the same place and is queryable through the same API.

## Endpoints

- `GET /health` — check if the backend is running
- `POST /sensors` — register a new sensor, get back an API key
- `GET /sensors` — list all sensors
- `GET /sensors/{id}` — get one sensor's details
- `POST /readings` — submit a reading (needs the x-api-key header)
- `GET /sensors/{id}/readings` — get recent readings for a sensor

## Stack

- Python 3.8+, FastAPI, SQLModel, SQLite, Uvicorn, paho-mqtt
- C++17 client with cpr, Eclipse Paho MQTT, nlohmann/json
- CMake with FetchContent for C++ dependencies
- Mosquitto MQTT broker
- pytest for backend tests
- GitHub Actions CI

## Running it

Install Mosquitto if you want MQTT:

    sudo apt install mosquitto mosquitto-clients

Set up the Python backend:

    git clone git@github.com:ssukumar2/sensorhub.git
    cd sensorhub
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://localhost:8000/docs to see the API.

For MQTT, run the subscriber in a separate terminal:

    python3 -m app.mqtt.subscriber

Build and run the C++ client:

    cd client-cpp
    cmake -B build && cmake --build build
    ./build/sensor_client --mode=http
    # or
    ./build/sensor_client --mode=mqtt

## Tests

    pytest tests/ -v

Six tests covering health check, sensor registration, API key authentication, and reading submission.

## License

MIT