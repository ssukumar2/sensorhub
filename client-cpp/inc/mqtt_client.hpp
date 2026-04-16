#pragma once

#include <string>

extern "C" 
{
#include "MQTTAsync.h"
}

// Thin C++ wrapper around Paho MQTT async client.
// Publishes JSON-encoded sensor readings to
//     sensorhub/sensors/{sensor_id}/readings
class MqttClient 
{
public:
    MqttClient(std::string broker_url, std::string client_id);
    ~MqttClient();

    MqttClient(const MqttClient&) = delete;
    MqttClient& operator=(const MqttClient&) = delete;

    // Connect to broker. Returns true on success.
    bool connect();

    // Disconnect cleanly.
    void disconnect();

    // Publish a reading. Returns true if the publish call was accepted.
    bool publish_reading(int sensor_id, double value, const std::string& unit);

private:
    std::string broker_url_;
    std::string client_id_;
    MQTTAsync client_{nullptr};
    bool connected_{false};
};