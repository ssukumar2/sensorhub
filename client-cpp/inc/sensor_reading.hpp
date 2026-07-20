#pragma once

#include <chrono>
#include <string>

/// Canonical value type for a single sensor reading.
/// Used consistently across HTTP, MQTT, CAN, UDP, and TCP paths.
struct SensorReading
{
    int sensor_id = 0;
    double value = 0.0;
    std::string unit;
    std::chrono::system_clock::time_point timestamp = std::chrono::system_clock::now();

    /// True if this reading was successfully submitted to the backend.
    bool submitted = false;

    /// Number of submission attempts made.
    int attempts = 0;
};
