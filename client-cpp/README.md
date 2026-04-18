# sensorhub C++ client

A C++ program that simulates a real sensor device. It connects to the sensorhub backend, registers itself, gets an API key, and starts sending temperature readings every 5 seconds. Works over both HTTP and MQTT.

## Building

From the client-cpp directory:

    cmake -B build
    cmake --build build

## Running

HTTP mode (default):

    ./build/sensor_client --mode=http

MQTT mode (needs Mosquitto broker running): cd sensor_client (again)

    ./build/sensor_client --mode=mqtt

Custom backend URL:

    ./build/sensor_client --backend=http://192.168.1.50:8000

## How it works

The client goes through these steps on startup:

1. Checks if the backend is healthy
2. Registers a new sensor and receives an API key
3. Starts a loop sending random temperature readings every 5 seconds
4. Each reading is signed with HMAC-SHA256 for integrity
5. Press Ctrl+C to stop cleanly

## Security

Every reading the client sends is protected with API key authentication, HMAC-SHA256 signatures covering the payload with a unique nonce and timestamp, and constant-time comparison on the server side to prevent timing attacks. The server rejects any request with a tampered payload or a timestamp older than 30 seconds.