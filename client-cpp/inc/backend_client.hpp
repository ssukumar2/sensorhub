#pragma once

#include <string>
#include <vector>

// Represents a registered sensor's identity returned by the backend.
struct SensorIdentity 
{
    int id;
    std::string api_key;
};

// Handles all HTTP communication with the sensorhub backend.
class BackendClient 
{
public:
    explicit BackendClient(std::string backend_url);

    // Returns true if backend responds with 200 on /health
    bool check_health();

    // Registers a sensor with the given name and location.
    // Returns the sensor identity (id + api_key) on success.
    // Throws std::runtime_error on failure.
    SensorIdentity register_sensor(const std::string& name, const std::string& location);

    // Submits a reading for the given sensor.
    // Returns true on success (201), false otherwise.
    bool submit_reading(const SensorIdentity& sensor, double value, const std::string& unit);

    // Returns true if sensor with given id exists on the backend.
    bool sensor_exists(int sensor_id);

    // Returns true if sensor with given id exists on the backend.
    bool sensor_exists(int sensor_id);

    // Submits multiple readings in one HMAC-signed request. Returns true on 201.
    struct ReadingItem { double value; std::string unit; };
    bool submit_batch(const SensorIdentity& sensor, const std::vector<ReadingItem>& items);

private:
    std::string backend_url_;
};