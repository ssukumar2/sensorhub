# sensor-client

C++ simulator that acts as a sensor device. Connects to the sensorhub backend,
registers itself, and pushes fake telemetry readings.

## Building

Open `client-cpp/` :

    cmake -B build
    cmake --build build

## Running

    ./build/sensor_client