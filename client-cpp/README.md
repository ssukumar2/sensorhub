# sensorhub C++ client

Sensor client for the sensorhub gateway. Sends signed telemetry over HTTP, MQTT, or CAN.

## Build

mkdir -p build && cd build
cmake ..
make -j$(nproc)

## Run

./sensor_client --help

### Options

- --mode=http|mqtt|can  transport (default http)
- --backend=URL  backend base url
- --mqtt=URL  mqtt broker url
- --can=IFACE  can interface (default vcan0)
- --name=NAME  sensor name
- --location=LOC  sensor location
- --interval=N  seconds between readings
- --log-level=debug|info|warn|error
- --no-health-check  disable background health polling
- --help  usage

## Components

- BackendClient  HTTP communication, HMAC-signed reading submission
- MqttClient  MQTT publishing
- CanTransport  CAN frame transport
- HmacSigner  HMAC-SHA256 request signing
- RetryPolicy  exponential backoff for transient failures
- HealthChecker  background backend health monitor
- Logger  level-based logging
- MetricsCollector  in-memory success/failure counters
